"""
OutOfBlack - Real-Time UAV Swarm Reconnaissance Backend.
FastAPI Application, WebSockets Broadcast & REST Mission Control API.
"""

from __future__ import annotations
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Set, List, Optional
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from simulation_engine import SimulationEngine
from models.telemetry import MissionSnapshot, POIEstimate
from models.commands import (
    BoundaryRequest,
    InjectPOIRequest,
    InspectPOIRequest,
    ResumeSearchRequest,
    SpeedRequest,
    BatterySwapRequest,
    RelaunchDroneRequest,
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

# Enable CORS for frontends (configurable via CORS_ORIGINS env var)
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").strip()
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ WebSocket Endpoint ------------------

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    Real-time 1 Hz stream of swarm telemetry, mesh topology,
    GSM blackout heatmap points, and detected victim POIs.
    Supports optional token-based authentication via WS_AUTH_TOKEN environment variable.
    """
    required_token = os.getenv("WS_AUTH_TOKEN", "").strip()
    if required_token:
        client_token = token or websocket.query_params.get("token") or websocket.headers.get("sec-websocket-protocol")
        if client_token != required_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning("Rejected unauthorized WebSocket connection attempt.")
            return

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


@app.post("/mission/abort", summary="Abort reconnaissance mission and order swarm to Return to Base (RTL)")
@app.post("/simulation/abort", summary="Abort reconnaissance mission and order swarm to Return to Base (RTL)")
async def abort_simulation():
    result = sim_engine.abort()
    logger.info(result.get("message"))
    return result


@app.post("/mission/swap-battery", summary="Replace depleted battery with fresh 100% pack for landed drone(s)")
async def swap_battery_endpoint(req: Optional[BatterySwapRequest] = None):
    d_id = req.drone_id if req else None
    result = sim_engine.swap_battery(drone_id=d_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    logger.info(result.get("message"))
    return result


@app.post("/mission/relaunch-drone", summary="Relaunch serviced drone(s) with fresh battery back into search mission")
async def relaunch_drone_endpoint(req: Optional[RelaunchDroneRequest] = None):
    d_id = req.drone_id if req else None
    result = sim_engine.relaunch_drone(drone_id=d_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    logger.info(result.get("message"))
    return result


@app.post("/simulation/reset", summary="Reset swarm to base, restore battery, clear POIs")
async def reset_simulation():
    global sim_speed_multiplier
    sim_speed_multiplier = 1.0
    sim_engine.reset()
    logger.info("Mission reset to default standby.")
    return {"status": "SUCCESS", "mission_state": sim_engine.mission_state, "speed_multiplier": sim_speed_multiplier}


@app.post("/simulation/speed", summary="Set simulation speed multiplier (e.g. 1.0, 2.0, 10.0, 25.0)")
async def set_simulation_speed(req: Optional[SpeedRequest] = None, multiplier: float = 1.0):
    global sim_speed_multiplier
    if req and req.multiplier is not None:
        mult = req.multiplier
    elif req and req.speed is not None:
        mult = req.speed
    else:
        mult = multiplier
    sim_speed_multiplier = max(0.25, min(50.0, float(mult)))
    logger.info(f"Simulation speed set to {sim_speed_multiplier}x")
    return {"status": "SUCCESS", "speed_multiplier": sim_speed_multiplier}


@app.post("/simulation/speed/{multiplier}", summary="Set simulation speed multiplier via URL")
async def set_simulation_speed_path(multiplier: float):
    global sim_speed_multiplier
    sim_speed_multiplier = max(0.25, min(50.0, multiplier))
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


@app.post("/mission/inspect-poi", summary="Dispatch drone to hover over detected signal POI")
async def inspect_poi_endpoint(req: InspectPOIRequest):
    result = sim_engine.inspect_poi(
        anonymized_id=req.anonymized_id,
        drone_id=req.drone_id,
        altitude_m=req.altitude_m,
        hover_duration_sec=req.hover_duration_sec,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or result.get("error", "Failed to dispatch drone to POI"))
    logger.info(f"Operator dispatched drone {result.get('drone_id')} to hover over POI {req.anonymized_id}")
    return result


@app.post("/mission/resume-search", summary="Resume swarm search patrol for inspecting drone")
async def resume_search_endpoint(req: Optional[ResumeSearchRequest] = None):
    d_id = req.drone_id if req else None
    result = sim_engine.resume_search(drone_id=d_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or result.get("error", "Failed to resume swarm search"))
    logger.info(f"Swarm search resumed: {result.get('resumed_drones')}")
    return result


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


@app.get("/config", summary="Frontend configuration for map tile providers")
async def get_config():
    """Returns map tile URLs for frontend dashboards (keys are proxied, not exposed raw)."""
    load_dotenv(override=True)
    carto_key = os.getenv("CARTO_API_KEY", "").strip()
    carto_url = os.getenv("CARTO_TILE_URL", "").strip()
    # Build ready-to-use tile URL so the frontend never sees the raw API key
    if not carto_url and carto_key:
        carto_url = f"https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png?key={carto_key}"
    elif not carto_url:
        carto_url = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    return {
        "carto_tile_url": carto_url,
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


@app.get("/", summary="API Root")
async def api_root():
    """OutOfBlack API root — frontend is served separately via Next.js."""
    return {
        "service": "OutOfBlack - UAV Swarm Reconnaissance API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/telemetry",
    }



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

