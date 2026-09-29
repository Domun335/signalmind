"""
OutOfBlack - Real-Time UAV Swarm Reconnaissance Backend.
FastAPI Application, WebSockets Broadcast, REST Mission Control & Tactical Dashboard.
"""

from __future__ import annotations
import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Set, List
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from simulation_engine import SimulationEngine
from models.telemetry import MissionSnapshot, POIEstimate
from models.commands import (
    BoundaryRequest,
    SimulationControlRequest,
    InjectPOIRequest,
    SimulationConfig,
)

# Load environment configuration from .env
load_dotenv()
CARTO_API_KEY = os.getenv("CARTO_API_KEY", "").strip()
CARTO_TILE_URL = os.getenv("CARTO_TILE_URL", "").strip()
MAPBOX_API_KEY = os.getenv("MAPBOX_API_KEY", "").strip()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [OutOfBlack] %(message)s",
)
logger = logging.getLogger("OutOfBlack")

# Global simulation instance
sim_engine = SimulationEngine()


class WebSocketConnectionManager:
    """Manages active real-time dashboard client connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, data: dict):
        if not self.active_connections:
            return

        # BUG-8 fix: snapshot the set to avoid RuntimeError from concurrent mutation
        connections_snapshot = list(self.active_connections)
        dead_connections = set()
        for connection in connections_snapshot:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send telemetry to client: {e}")
                dead_connections.add(connection)

        for dead in dead_connections:
            self.active_connections.discard(dead)


ws_manager = WebSocketConnectionManager()
simulation_task: asyncio.Task | None = None
sim_speed_multiplier: float = 1.0


async def simulation_ticker_loop():
    """1 Hz background simulation loop emitting telemetry snapshots."""
    global sim_speed_multiplier
    logger.info("Starting OutOfBlack 1 Hz simulation ticker loop.")
    while True:
        try:
            # Sub-stepping: execute simulation steps in increments of <= 0.5s for numerical stability
            remaining_dt = max(0.1, sim_speed_multiplier)
            sub_step = 0.5
            last_snapshot = None
            while remaining_dt > 0.001:
                cur_dt = min(sub_step, remaining_dt)
                last_snapshot = sim_engine.step(dt_sec=cur_dt)
                remaining_dt -= cur_dt

            if last_snapshot:
                payload = last_snapshot.model_dump(mode="json")
                await ws_manager.broadcast_json(payload)
        except asyncio.CancelledError:
            logger.info("Simulation ticker loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in simulation ticker loop: {e}", exc_info=True)

        await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global simulation_task
    # Automatically start simulation ticker in background
    simulation_task = asyncio.create_task(simulation_ticker_loop())
    logger.info("OutOfBlack Tactical Backend online.")
    yield
    # Shutdown
    if simulation_task:
        simulation_task.cancel()
        try:
            await simulation_task
        except asyncio.CancelledError:
            pass
    logger.info("OutOfBlack Tactical Backend stopped.")


app = FastAPI(
    title="OutOfBlack - Dual-Use UAV Swarm Reconnaissance",
    description="Real-time P2P Mesh UAV swarm simulator for passive RF localization in blackout crisis zones.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for external frontends (e.g. Next.js, Vite, Leaflet, Mapbox)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ WebSocket Endpoint ------------------

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    Real-time 1 Hz stream of swarm telemetry, mesh topology,
    GSM blackout heatmap points, and detected victim POIs.
    """
    await ws_manager.connect(websocket)
    # Immediately send current state on connection
    try:
        initial_state = sim_engine.step(0.0).model_dump(mode="json")
        await websocket.send_json(initial_state)
        # Keep connection open for client messages (heartbeat/pings)
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


# ------------------ REST Mission Control ------------------

@app.post("/simulation/start", summary="Start or resume swarm reconnaissance mission")
async def start_simulation():
    sim_engine.start()
    logger.info("Mission started.")
    return {"status": "SUCCESS", "mission_state": sim_engine.mission_state}


@app.post("/simulation/pause", summary="Pause swarm kinematics and RF emission")
async def pause_simulation():
    sim_engine.pause()
    logger.info("Mission paused.")
    return {"status": "SUCCESS", "mission_state": sim_engine.mission_state}


@app.post("/simulation/resume", summary="Resume paused mission")
async def resume_simulation():
    sim_engine.resume()
    logger.info("Mission resumed.")
    return {"status": "SUCCESS", "mission_state": sim_engine.mission_state}


@app.post("/simulation/reset", summary="Reset swarm to base, restore battery, clear POIs")
async def reset_simulation():
    global sim_speed_multiplier
    sim_speed_multiplier = 1.0
    sim_engine.reset()
    logger.info("Mission reset to default standby.")
    return {"status": "SUCCESS", "mission_state": sim_engine.mission_state, "speed_multiplier": sim_speed_multiplier}


@app.post("/simulation/speed", summary="Set simulation speed multiplier (e.g. 1.0, 2.0, 5.0, 10.0)")
async def set_simulation_speed(data: dict = None, multiplier: float = 1.0):
    global sim_speed_multiplier
    if data and "multiplier" in data:
        mult = float(data["multiplier"])
    elif data and "speed" in data:
        mult = float(data["speed"])
    else:
        mult = float(multiplier)
    sim_speed_multiplier = max(0.25, min(20.0, mult))
    logger.info(f"Simulation speed set to {sim_speed_multiplier}x")
    return {"status": "SUCCESS", "speed_multiplier": sim_speed_multiplier}


@app.post("/simulation/speed/{multiplier}", summary="Set simulation speed multiplier via URL")
async def set_simulation_speed_path(multiplier: float):
    global sim_speed_multiplier
    sim_speed_multiplier = max(0.25, min(20.0, multiplier))
    logger.info(f"Simulation speed set to {sim_speed_multiplier}x")
    return {"status": "SUCCESS", "speed_multiplier": sim_speed_multiplier}


@app.get("/simulation/speed", summary="Get current simulation speed multiplier")
async def get_simulation_speed():
    return {"speed_multiplier": sim_speed_multiplier}


@app.post("/mission/define-boundary", summary="Redefine tactical search boundary via GeoJSON / Bounding Box")
async def define_boundary(req: BoundaryRequest):
    coords = None
    if req.polygon:
        coords = [(p.lat, p.lon) for p in req.polygon]
    sim_engine.define_boundary(polygon_coords=coords, bbox=req.bbox)
    logger.info("Tactical boundary redefined.")
    return {
        "status": "SUCCESS",
        "bounds_m": {
            "width": sim_engine.bounds.width,
            "height": sim_engine.bounds.height,
        },
        "gcs_position": {
            "lat": sim_engine.geo_ref.to_geo(sim_engine.gcs_pos.x, sim_engine.gcs_pos.y).lat,
            "lon": sim_engine.geo_ref.to_geo(sim_engine.gcs_pos.x, sim_engine.gcs_pos.y).lon,
        }
    }


@app.post("/simulation/inject-poi", summary="Inject a trapped victim device for demonstration")
async def inject_poi(req: InjectPOIRequest):
    anon_id = sim_engine.inject_poi(
        lat=req.lat,
        lon=req.lon,
        signal_type=req.signal_type,
        raw_mac=req.raw_mac,
        tx_power_dbm=req.tx_power_dbm,
    )
    logger.info(f"Injected custom victim emitter: {anon_id} at ({req.lat}, {req.lon})")
    return {
        "status": "SUCCESS",
        "anonymized_id": anon_id,
        "lat": req.lat,
        "lon": req.lon,
    }


@app.get("/simulation/state", response_model=MissionSnapshot, summary="Current simulation snapshot")
async def get_simulation_state():
    return sim_engine.step(0.0)


@app.get("/simulation/pois", response_model=List[POIEstimate], summary="List of actively localized victim POIs")
async def get_pois():
    return sim_engine.poi_tracker.get_all_estimates(sim_engine.geo_ref, current_sim_time=sim_engine.elapsed_time_sec)


@app.get("/health", summary="Health check endpoint")
async def health_check():
    return {
        "status": "HEALTHY",
        "mission_state": sim_engine.mission_state,
        "active_drones": len(sim_engine.drones),
        "connected_ws_clients": len(ws_manager.active_connections),
    }


@app.get("/config", summary="Frontend configuration and map service credentials")
async def get_config():
    """Returns map provider keys and URLs for frontend dashboards."""
    load_dotenv(override=True)
    return {
        "carto_api_key": os.getenv("CARTO_API_KEY", "").strip(),
        "carto_tile_url": os.getenv("CARTO_TILE_URL", "").strip(),
        "mapbox_api_key": os.getenv("MAPBOX_API_KEY", "").strip(),
    }


@app.get("/simulation/config", summary="Get all active simulation parameters")
async def get_simulation_config():
    """Returns all simulation parameters (UAV swarm, RF propagation, Mesh, GSM, victims) as JSON."""
    return sim_engine.settings.to_dict()


@app.post("/simulation/config", summary="Update simulation parameters and reload swarm")
async def update_simulation_config(new_config: dict):
    """Updates simulation settings dynamically, saves to simulation_config.json, and reloads the engine."""
    global sim_engine
    try:
        from config import (
            SimulationSettings,
            AreaConfig,
            SwarmConfig,
            RFPropagationConfig,
            MeshNetworkConfig,
            GSMBlackoutConfig,
            EstimationConfig,
            VictimScenario,
        )

        settings = SimulationSettings(
            area=AreaConfig(**new_config.get("area", sim_engine.settings.area.__dict__)),
            swarm=SwarmConfig(**new_config.get("swarm", sim_engine.settings.swarm.__dict__)),
            rf=RFPropagationConfig(**new_config.get("rf", sim_engine.settings.rf.__dict__)),
            mesh=MeshNetworkConfig(**new_config.get("mesh", sim_engine.settings.mesh.__dict__)),
            gsm=GSMBlackoutConfig(**new_config.get("gsm", sim_engine.settings.gsm.__dict__)),
            estimation=EstimationConfig(**new_config.get("estimation", sim_engine.settings.estimation.__dict__)),
            victims=[
                VictimScenario(**v) for v in new_config.get("victims", [v.__dict__ for v in sim_engine.settings.victims])
            ],
        )
        settings.save_to_file("simulation_config.json")
        # BUG-3 fix: create a fresh instance instead of calling __init__ on the live object
        sim_engine = SimulationEngine(settings=settings)
        return {
            "status": "SUCCESS",
            "message": "Configuration updated and applied to running simulation",
            "config": settings.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration format: {e}")


# ------------------ Tactical Web Dashboard (Built-in Demo) ------------------

@app.get("/", response_class=HTMLResponse, summary="Tactical Operations Dashboard")
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """
    Complete, self-contained tactical Leaflet GIS operations dashboard.
    Visualizes drones, mesh links, blackout gradient, and victim uncertainty circles.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OutOfBlack // Tactical UAV Swarm Reconnaissance</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0a0e17;
      --panel-bg: rgba(13, 20, 36, 0.85);
      --panel-border: rgba(30, 58, 110, 0.45);
      --accent-cyan: #00f0ff;
      --accent-green: #00ff88;
      --accent-amber: #ffb700;
      --accent-red: #ff3366;
      --text-main: #f0f4fc;
      --text-muted: #8899b7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Outfit', sans-serif;
      overflow: hidden;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: rgba(10, 14, 23, 0.95);
      border-bottom: 1px solid var(--panel-border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 1000;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge-dual-use {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      padding: 3px 8px;
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid var(--accent-cyan);
      color: var(--accent-cyan);
      border-radius: 4px;
    }
    h1 {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #fff;
    }
    .controls {
      display: flex;
      gap: 10px;
    }
    button {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 600;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.2s;
    }
    .btn-start { background: #00a86b; color: #fff; }
    .btn-start:hover { background: #00c880; }
    .btn-pause { background: #d97706; color: #fff; }
    .btn-pause:hover { background: #f59e0b; }
    .btn-reset { background: #374151; color: #e5e7eb; border-color: #4b5563; }
    .btn-reset:hover { background: #4b5563; }
    .btn-inject { background: rgba(255, 51, 102, 0.2); border-color: var(--accent-red); color: var(--accent-red); }
    .btn-inject:hover { background: rgba(255, 51, 102, 0.4); }
    .btn-toggle {
      background: rgba(168, 85, 247, 0.15);
      border-color: #a855f7;
      color: #d8b4fe;
    }
    .btn-toggle:hover {
      background: rgba(168, 85, 247, 0.35);
    }
    .btn-toggle.active {
      background: #9333ea;
      color: #fff;
      box-shadow: 0 0 12px rgba(168, 85, 247, 0.5);
    }
    .speed-group {
      display: flex;
      align-items: center;
      gap: 3px;
      background: rgba(16, 26, 48, 0.85);
      border: 1px solid var(--panel-border);
      border-radius: 6px;
      padding: 3px 6px;
      margin-left: 6px;
    }
    .speed-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      color: var(--text-muted);
      margin-right: 3px;
      letter-spacing: 0.5px;
    }
    .btn-speed {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 8px;
      border-radius: 4px;
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-speed:hover {
      background: rgba(0, 240, 255, 0.15);
      color: #fff;
    }
    .btn-speed.active {
      background: rgba(0, 240, 255, 0.25);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
      box-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }

    .main-container {
      flex: 1;
      display: flex;
      position: relative;
      overflow: hidden;
    }
    #map {
      flex: 1;
      height: 100%;
      background: #090c14;
    }

    /* Sidebar Telemetry */
    .sidebar {
      position: absolute;
      top: 16px;
      right: 16px;
      bottom: 16px;
      width: 360px;
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
      overflow: hidden;
    }
    .sidebar-header {
      padding: 14px 18px;
      border-bottom: 1px solid var(--panel-border);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--accent-cyan);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .sidebar-content {
      padding: 14px;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .metric-box {
      background: rgba(20, 32, 58, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 10px;
    }
    .metric-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
    }
    .metric-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 18px;
      font-weight: 700;
      margin-top: 4px;
      color: #fff;
    }
    .val-cyan { color: var(--accent-cyan); }
    .val-green { color: var(--accent-green); }
    .val-amber { color: var(--accent-amber); }
    .val-red { color: var(--accent-red); }

    .section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-muted);
      font-weight: 700;
      margin-bottom: 8px;
    }
    .drone-card {
      background: rgba(16, 26, 48, 0.7);
      border: 1px solid rgba(0, 240, 255, 0.15);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 8px;
      font-size: 12px;
    }
    .drone-card.is-gateway {
      border-color: var(--accent-amber);
      background: rgba(255, 183, 0, 0.08);
    }
    .drone-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 4px;
    }
    .drone-name {
      font-weight: 700;
      color: #fff;
    }
    .role-badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(0, 240, 255, 0.2);
      color: var(--accent-cyan);
    }
    .role-badge.gateway {
      background: rgba(255, 183, 0, 0.25);
      color: var(--accent-amber);
    }

    .poi-card {
      background: rgba(255, 51, 102, 0.08);
      border: 1px solid rgba(255, 51, 102, 0.3);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 8px;
      font-size: 12px;
    }
    .poi-id {
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      color: var(--accent-red);
    }

    .leaflet-control-layers {
      background: var(--panel-bg) !important;
      border: 1px solid var(--panel-border) !important;
      border-radius: 8px !important;
      color: #fff !important;
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 11px !important;
      padding: 8px 12px !important;
      box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
      backdrop-filter: blur(10px);
    }
    .leaflet-control-layers-base label {
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 4px;
      color: var(--text-main);
    }

    /* Tactical POI (Victim Signal) Beacon & Radar Ripple */
    .poi-beacon-wrapper {
      position: relative;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .poi-beacon-core {
      width: 14px;
      height: 14px;
      background: #ff3366;
      border: 2px solid #ffffff;
      border-radius: 50%;
      box-shadow: 0 0 10px rgba(255, 51, 102, 0.9);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2;
    }
    .poi-beacon-ripple {
      position: absolute;
      width: 14px;
      height: 14px;
      border: 2px solid #ff3366;
      border-radius: 50%;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      animation: poiRipple 2.2s cubic-bezier(0.1, 0.8, 0.2, 1) infinite;
      pointer-events: none;
    }
    .poi-beacon-ripple.delay {
      animation-delay: 1.1s;
    }
    @keyframes poiRipple {
      0% {
        width: 14px;
        height: 14px;
        opacity: 0.9;
      }
      100% {
        width: 48px;
        height: 48px;
        opacity: 0;
      }
    }
    .poi-beacon-label {
      position: absolute;
      top: -18px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(17, 24, 39, 0.9);
      border: 1px solid rgba(255, 51, 102, 0.6);
      color: #ff3366;
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 3px;
      white-space: nowrap;
      pointer-events: none;
      box-shadow: 0 2px 6px rgba(0,0,0,0.6);
    }
    .status-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-green);
      margin-right: 6px;
    }
  </style>
</head>
<body>

<header>
  <div class="brand">
    <span class="badge-dual-use">Dual-Use Tactical Recon</span>
    <h1>OutOfBlack // Swarm RF Search & Rescue</h1>
  </div>
  <div class="controls">
    <button class="btn-start" onclick="sendControl('start')">▶ START SWARM</button>
    <button class="btn-pause" onclick="sendControl('pause')">⏸ PAUSE</button>
    <button class="btn-reset" onclick="sendControl('reset')">↺ RESET</button>
    <button class="btn-inject" onclick="injectRandomVictim()">+ INJECT VICTIM</button>
    <button id="btnTogglePaths" class="btn-toggle active" onclick="toggleFlightPaths()">🛣️ TRASY PLANOWANE [WŁ]</button>
    <div class="speed-group">
      <span class="speed-label">WARP:</span>
      <button class="btn-speed active" id="spd1" onclick="setSpeed(1.0)">1x</button>
      <button class="btn-speed" id="spd2" onclick="setSpeed(2.0)">2x</button>
      <button class="btn-speed" id="spd5" onclick="setSpeed(5.0)">5x</button>
      <button class="btn-speed" id="spd10" onclick="setSpeed(10.0)">10x</button>
    </div>
  </div>
</header>

<div class="main-container">
  <div id="map"></div>

  <div class="sidebar">
    <div class="sidebar-header">
      <div><span class="status-dot" id="liveDot"></span>LIVE MISSION TELEMETRY</div>
      <span id="missionState" style="color:var(--accent-green); font-family:'JetBrains Mono'">IDLE</span>
    </div>
    <div class="sidebar-content">
      <div class="metric-grid">
        <div class="metric-box">
          <div class="metric-label">Elapsed Time</div>
          <div class="metric-val val-cyan" id="mTime">0.0s</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Area Covered</div>
          <div class="metric-val val-green" id="mArea">0%</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Mesh Links</div>
          <div class="metric-val val-amber" id="mMesh">0 active</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Detected POIs</div>
          <div class="metric-val val-red" id="mPois">0 found</div>
        </div>
      </div>

      <div>
        <div class="section-title">Swarm Nodes (P2P Mesh)</div>
        <div id="droneList"></div>
      </div>

      <div>
        <div class="section-title">Localized Victims (Shrinking Uncertainty)</div>
        <div id="poiList"></div>
      </div>
    </div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  // Initialize Leaflet Map with Carto Dark Tiles
  const map = L.map('map', {
    zoomControl: false,
    attributionControl: false
  }).setView([50.0614, 19.9366], 15);

  const envCartoKey = "__CARTO_API_KEY__";
  const envCartoUrl = "__CARTO_TILE_URL__";

  let cartoUrl = envCartoUrl;
  if (!cartoUrl) {
    cartoUrl = envCartoKey 
      ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${envCartoKey}`
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
  }

  const cartoDarkLayer = L.tileLayer(cartoUrl, {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; CARTO'
  });

  const esriDarkLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16,
    attribution: '&copy; Esri'
  });

  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '&copy; Esri World Imagery'
  });

  // Layer groups for dynamic elements
  const boundaryLayer = L.layerGroup().addTo(map);
  const flightPathsLayer = L.layerGroup().addTo(map);
  const gsmGridLayer = L.layerGroup().addTo(map);
  const meshLinesLayer = L.layerGroup().addTo(map);
  const gcsRangeLayer = L.layerGroup().addTo(map);
  const meshRangeLayer = L.layerGroup().addTo(map);
  const dronesLayer = L.layerGroup().addTo(map);
  const poisLayer = L.layerGroup().addTo(map);
  const gcsLayer = L.layerGroup().addTo(map);

  let showFlightPaths = true;
  function toggleFlightPaths() {
    showFlightPaths = !showFlightPaths;
    const btn = document.getElementById('btnTogglePaths');
    if (showFlightPaths) {
      if (!map.hasLayer(flightPathsLayer)) map.addLayer(flightPathsLayer);
      if (btn) { btn.classList.add('active'); btn.textContent = '🛣️ TRASY PLANOWANE [WŁ]'; }
    } else {
      if (map.hasLayer(flightPathsLayer)) map.removeLayer(flightPathsLayer);
      if (btn) { btn.classList.remove('active'); btn.textContent = '🛣️ TRASY PLANOWANE [WYŁ]'; }
    }
  }

  L.control.layers(
    {
      "CARTO Dark Matter (z kluczem)": cartoDarkLayer,
      "Esri Dark Canvas (bez znaku wodnego)": esriDarkLayer,
      "Satelita (Esri Imagery)": satelliteLayer
    },
    {
      "📡 Linki sieci Mesh": meshLinesLayer,
      "⭕ Zasięg stacji GCS (C2)": gcsRangeLayer,
      "⭕ Zasięg P2P Dronów (Mesh)": meshRangeLayer,
      "🛣️ Planowane trasy UAV": flightPathsLayer,
      "📶 Gradient Blackoutu GSM": gsmGridLayer
    },
    { position: 'topleft' }
  ).addTo(map);

  L.control.zoom({ position: 'bottomleft' }).addTo(map);

  let initialCenterSet = false;

  // Custom Icon Helpers
  function createDroneIcon(callsign, heading, isGateway) {
    const color = isGateway ? '#ffb700' : '#00f0ff';
    const border = isGateway ? '#ffb700' : '#0099ff';
    return L.divIcon({
      className: 'drone-marker',
      html: `
        <div style="transform: rotate(${heading}deg); width:28px; height:28px; display:flex; align-items:center; justify-content:center;">
          <svg viewBox="0 0 24 24" width="26" height="26" fill="${color}" stroke="${border}" stroke-width="1.5">
            <polygon points="12 2, 19 21, 12 17, 5 21" />
          </svg>
        </div>
        <div style="font-family:'JetBrains Mono'; font-size:10px; font-weight:700; color:#fff; text-shadow:0 0 4px #000; text-align:center; margin-top:-2px;">
          ${callsign}
        </div>
      `,
      iconSize: [36, 44],
      iconAnchor: [18, 14]
    });
  }

  function createGcsIcon() {
    return L.divIcon({
      className: 'gcs-marker',
      html: `
        <div style="width:24px; height:24px; background:#10b981; border:2px solid #fff; border-radius:4px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px #10b981;">
          <span style="font-size:12px; font-weight:bold; color:#000;">G</span>
        </div>
        <div style="font-family:'JetBrains Mono'; font-size:10px; font-weight:700; color:#10b981; text-align:center;">GCS</div>
      `,
      iconSize: [30, 36],
      iconAnchor: [15, 12]
    });
  }

  // WebSocket Telemetry Connection
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/telemetry`;
  let socket = null;

  function connectWebSocket() {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[OutOfBlack] Connected to telemetry stream.");
      document.getElementById('liveDot').style.background = '#00ff88';
    };

    socket.onmessage = (event) => {
      const snapshot = JSON.parse(event.data);
      renderSimulation(snapshot);
    };

    socket.onclose = () => {
      console.log("[OutOfBlack] WebSocket closed. Reconnecting in 2s...");
      document.getElementById('liveDot').style.background = '#ff3366';
      setTimeout(connectWebSocket, 2000);
    };
  }

  function renderSimulation(data) {
    // 1. Center map on first frame
    if (!initialCenterSet && data.boundary && data.boundary.length > 0) {
      const bounds = L.latLngBounds(data.boundary);
      map.fitBounds(bounds, { padding: [40, 40] });
      initialCenterSet = true;
    }

    // 2. Mission status & metrics
    document.getElementById('missionState').textContent = data.mission_state;
    document.getElementById('mTime').textContent = `${data.stats.elapsed_time_sec.toFixed(0)}s`;
    document.getElementById('mArea').textContent = `${data.stats.area_covered_pct}%`;
    const gcsConnected = (data.mesh && data.mesh.gcs_connected);
    const gwId = (data.mesh && data.mesh.gateway_id) ? data.mesh.gateway_id : 'BRAK';
    document.getElementById('mMesh').textContent = `${data.stats.mesh_links_count} linków (${gcsConnected ? 'GCS ' + gwId : 'OFFLINE'})`;
    document.getElementById('mPois').textContent = `${data.stats.pois_discovered} found`;

    // 3. Render Boundary Polygon
    boundaryLayer.clearLayers();
    if (data.boundary) {
      L.polygon(data.boundary, {
        color: '#00f0ff',
        weight: 1.5,
        fillColor: '#00f0ff',
        fillOpacity: 0.02,
        dashArray: '4, 6'
      }).addTo(boundaryLayer);
    }

    // 4. Render GSM Blackout Grid (sparse dot gradient)
    if (gsmGridLayer.getLayers().length === 0 && data.gsm_grid) {
      data.gsm_grid.forEach(pt => {
        let color = '#10b981';
        let opacity = 0.15;
        if (pt.status === 'DEGRADED') { color = '#f59e0b'; opacity = 0.3; }
        if (pt.status === 'BLACKOUT') { color = '#ef4444'; opacity = 0.45; }

        L.circle([pt.lat, pt.lon], {
          radius: 65,
          stroke: false,
          fillColor: color,
          fillOpacity: opacity
        }).addTo(gsmGridLayer);
      });
    }

    // 5. Render GCS and C2 Range Circle
    gcsLayer.clearLayers();
    gcsRangeLayer.clearLayers();
    if (data.gcs_position) {
      L.marker([data.gcs_position.lat, data.gcs_position.lon], {
        icon: createGcsIcon()
      }).bindTooltip("<b>GCS (Ground Control Station)</b><br>Stanowisko dowodzenia & lądowisko", { sticky: true }).addTo(gcsLayer);

      const gcsRangeM = (data.mesh && data.mesh.gcs_range_m) ? data.mesh.gcs_range_m : 5000.0;
      L.circle([data.gcs_position.lat, data.gcs_position.lon], {
        radius: gcsRangeM,
        color: '#ffb700',
        weight: 1.5,
        dashArray: '8, 8',
        fillColor: '#ffb700',
        fillOpacity: 0.03
      }).bindTooltip(`<b>Zasięg C2 GCS</b>: ${gcsRangeM}m (${(gcsRangeM/1000).toFixed(1)} km)`, { sticky: true }).addTo(gcsRangeLayer);
    }

    // 6. Render Mesh Network Edges & P2P Range Circle
    meshLinesLayer.clearLayers();
    meshRangeLayer.clearLayers();
    const nodeLookup = {};
    if (data.mesh && data.mesh.nodes) {
      data.mesh.nodes.forEach(n => { nodeLookup[n.id] = [n.lat, n.lon]; });
    }

    const p2pRangeM = (data.mesh && data.mesh.mesh_range_m) ? data.mesh.mesh_range_m : 2500.0;

    // Draw P2P Mesh Range circle around the primary Gateway drone
    if (data.mesh && data.mesh.gateway_id && nodeLookup[data.mesh.gateway_id]) {
      const gwPos = nodeLookup[data.mesh.gateway_id];
      L.circle(gwPos, {
        radius: p2pRangeM,
        color: '#00f0ff',
        weight: 1.2,
        dashArray: '5, 8',
        fillColor: '#00f0ff',
        fillOpacity: 0.03
      }).bindTooltip(`<b>Zasięg P2P Drona-Bramy (${data.mesh.gateway_id})</b>: ${p2pRangeM}m (${(p2pRangeM/1000).toFixed(1)} km)`, { sticky: true }).addTo(meshRangeLayer);
    }

    if (data.mesh && data.mesh.edges) {
      data.mesh.edges.forEach(edge => {
        const p1 = nodeLookup[edge.source];
        const p2 = nodeLookup[edge.target];
        if (p1 && p2) {
          const isGcsLink = edge.is_gateway_link || (edge.source === 'GCS-BASE' || edge.target === 'GCS-BASE');
          const lineColor = isGcsLink ? '#ffb700' : '#00f0ff';
          const weight = isGcsLink ? 3.0 : 1.8;
          const opacity = isGcsLink ? 0.95 : 0.75;

          const poly = L.polyline([p1, p2], {
            color: lineColor,
            weight: weight,
            opacity: opacity,
            dashArray: isGcsLink ? '4, 6' : null
          }).addTo(meshLinesLayer);

          const linkType = isGcsLink ? '⚡ C2 GATEWAY UPLINK' : '🔗 P2P AIR-TO-AIR MESH';
          poly.bindTooltip(
            `<div style="font-family:'JetBrains Mono',monospace; font-size:11px;">
              <b style="color:${lineColor}">${linkType}</b><br>
              ${edge.source} ↔ ${edge.target}<br>
              Dystans: <b>${edge.distance_m}m</b><br>
              RSSI: <b>${edge.rssi_dbm} dBm</b> | Jakość: <b>${edge.quality_pct}%</b>
            </div>`,
            { sticky: true }
          );
        }
      });
    }

    // 6. Render Planned Flight Paths
    flightPathsLayer.clearLayers();
    const droneColors = ['#00f0ff', '#00ff88', '#ffb700', '#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f97316'];
    if (data.drones) {
      data.drones.forEach((d, idx) => {
        if (d.planned_path && d.planned_path.length > 1) {
          const color = droneColors[idx % droneColors.length];
          L.polyline(d.planned_path, {
            color: color,
            weight: 2,
            dashArray: '5, 8',
            opacity: 0.65
          }).addTo(flightPathsLayer);

          d.planned_path.forEach((pt, wpIdx) => {
            if (wpIdx > 0 && wpIdx < d.planned_path.length - 1) {
              L.circleMarker(pt, {
                radius: 3,
                color: color,
                fillColor: color,
                fillOpacity: 0.8,
                weight: 1
              }).addTo(flightPathsLayer);
            }
          });
        }
      });
    }

    // 7. Render Drones
    dronesLayer.clearLayers();
    const droneListEl = document.getElementById('droneList');
    droneListEl.innerHTML = '';

    data.drones.forEach(d => {
      // Map marker
      L.marker([d.lat, d.lon], {
        icon: createDroneIcon(d.callsign, d.heading_deg, d.is_gateway)
      }).addTo(dronesLayer);

      // Sidebar card
      const card = document.createElement('div');
      card.className = `drone-card ${d.is_gateway ? 'is-gateway' : ''}`;
      const route = (data.mesh && data.mesh.routes_to_gcs && data.mesh.routes_to_gcs[d.id])
        ? data.mesh.routes_to_gcs[d.id].join(' ➔ ')
        : (d.is_gateway ? 'BEZPOŚREDNI C2' : 'POZA ZASIĘGIEM');
      card.innerHTML = `
        <div class="drone-row">
          <span class="drone-name">${d.id} // ${d.callsign}</span>
          <span class="role-badge ${d.is_gateway ? 'gateway' : ''}">${d.is_gateway ? '★ GATEWAY' : d.role}</span>
        </div>
        <div class="drone-row" style="color:var(--text-muted); font-size:11px;">
          <span>ALT: ${d.alt_m}m | SPD: ${d.speed_mps}m/s</span>
          <span>BAT: ${d.battery_pct}%</span>
        </div>
        <div class="drone-row" style="color:var(--text-muted); font-size:11px;">
          <span>Status: ${d.status}</span>
          <span style="color:var(--accent-cyan)">Pakiety RF: ${d.packets_sniffed}</span>
        </div>
        <div class="drone-row" style="color:${d.is_gateway ? 'var(--accent-amber)' : 'var(--accent-cyan)'}; font-size:10px; margin-top:3px; font-family:'JetBrains Mono';">
          <span>Routing: ${route}</span>
        </div>
      `;
      droneListEl.appendChild(card);
    });

    // 8. Render POIs (Localized Victims with Uncertainty Circles)
    poisLayer.clearLayers();
    const poiListEl = document.getElementById('poiList');
    poiListEl.innerHTML = '';

    if (data.pois.length === 0) {
      poiListEl.innerHTML = '<div style="color:var(--text-muted); font-size:11px;">Scanning blackout sector for RF probes...</div>';
    } else {
      data.pois.forEach(poi => {
        // 1. Precise geodetic uncertainty area (CEP radius) - strictly anchored to coordinates
        L.circle([poi.est_lat, poi.est_lon], {
          radius: poi.uncertainty_radius_m,
          color: '#ff3366',
          weight: 1.5,
          dashArray: '5, 6',
          fillColor: '#ff3366',
          fillOpacity: 0.12,
          interactive: false
        }).addTo(poisLayer);

        // 2. Tactical Beacon Icon with concentric in-place ripple (no diagonal sliding)
        const poiIcon = L.divIcon({
          className: 'poi-marker-div',
          html: `
            <div class="poi-beacon-wrapper">
              <div class="poi-beacon-ripple"></div>
              <div class="poi-beacon-ripple delay"></div>
              <div class="poi-beacon-core">
                <span style="font-size:8px; line-height:1; color:#fff;">●</span>
              </div>
              <div class="poi-beacon-label">±${poi.uncertainty_radius_m.toFixed(0)}m</div>
            </div>
          `,
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });

        const marker = L.marker([poi.est_lat, poi.est_lon], { icon: poiIcon }).addTo(poisLayer);
        marker.bindTooltip(
          `<div style="font-family:'JetBrains Mono',monospace; font-size:11px; padding:3px;">
            <b style="color:#ff3366;">🎯 WYKRYTY SYGNAŁ RF (OFIARA)</b><br>
            ID: <b>${poi.anonymized_id}</b><br>
            Typ: <b>${poi.signal_type}</b><br>
            Niepewność CEP: <b>±${poi.uncertainty_radius_m} m</b><br>
            Pewność: <b>${Math.round(poi.confidence * 100)}%</b><br>
            Odebrane pakiety: <b>${poi.detections_count}</b><br>
            Ostatnie RSSI: <b>${poi.last_rssi_dbm} dBm</b><br>
            Wykryty przez: <b>${poi.sniffed_by_drones.join(', ')}</b>
          </div>`,
          { sticky: true }
        );

        // 3. Sidebar card with click-to-focus on map
        const pcard = document.createElement('div');
        pcard.className = 'poi-card';
        pcard.style.cursor = 'pointer';
        pcard.onclick = () => {
          map.setView([poi.est_lat, poi.est_lon], 16);
          marker.openTooltip();
        };
        pcard.innerHTML = `
          <div class="drone-row">
            <span class="poi-id">${poi.anonymized_id}</span>
            <span style="font-family:'JetBrains Mono'; color:var(--accent-green); font-weight:700;">${Math.round(poi.confidence * 100)}% CONF</span>
          </div>
          <div class="drone-row" style="color:var(--text-muted); font-size:11px; margin-top:4px;">
            <span>Niepewność: ±${poi.uncertainty_radius_m}m</span>
            <span>Impulsy: ${poi.detections_count}</span>
          </div>
          <div class="drone-row" style="color:var(--text-muted); font-size:10px;">
            <span>${poi.signal_type}</span>
            <span>RSSI: ${poi.last_rssi_dbm} dBm</span>
          </div>
        `;
        poiListEl.appendChild(pcard);
      });
    }
  }

  let currentSpeed = 1.0;
  async function setSpeed(mult) {
    currentSpeed = mult;
    ['spd1', 'spd2', 'spd5', 'spd10'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('active');
    });
    const activeBtn = document.getElementById(`spd${mult}`);
    if (activeBtn) activeBtn.classList.add('active');

    try {
      await fetch('/simulation/speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ multiplier: mult })
      });
    } catch (e) {
      console.error("Speed change error:", e);
    }
  }

  // REST Control Actions
  async function sendControl(action) {
    try {
      await fetch(`/simulation/${action}`, { method: 'POST' });
      if (action === 'reset') {
        setSpeed(1.0);
      }
    } catch (e) {
      console.error("Control error:", e);
    }
  }

  async function injectRandomVictim() {
    // Generate point inside boundary
    const lat = 50.0614 + (Math.random() - 0.5) * 0.008;
    const lon = 19.9366 + (Math.random() - 0.5) * 0.008;
    try {
      await fetch('/simulation/inject-poi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat: lat,
          lon: lon,
          signal_type: 'WIFI_PROBE_REQ',
          tx_power_dbm: 16.0
        })
      });
    } catch (e) {
      console.error("Inject error:", e);
    }
  }

  // Start WebSocket
  connectWebSocket();
</script>

</body>
</html>
    """
    load_dotenv(override=True)
    active_carto_key = os.getenv("CARTO_API_KEY", "").strip()
    active_carto_url = os.getenv("CARTO_TILE_URL", "").strip()

    rendered_html = (
        html_content
        .replace("__CARTO_API_KEY__", active_carto_key)
        .replace("__CARTO_TILE_URL__", active_carto_url)
    )
    return HTMLResponse(content=rendered_html)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
