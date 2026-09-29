"""
OutOfBlack - Central Swarm Simulation Engine.
Coordinates UAV kinematics, RF propagation, Mesh P2P routing, GSM blackout, and POI localization.
"""

from __future__ import annotations
import os
import math
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set

from core.coordinates import GeoPoint, LocalPoint3D, GeoReference, SearchAreaBounds
from core.flight_planner import BoustrophedonPlanner, DroneKinematics, Waypoint
from core.rf_propagation import LogDistancePathLoss, GSMBlackoutEnvironment, GroundEmitter
from core.mesh_network import MeshRouter
from core.estimator import POITracker
from config import SIM_CONFIG, SimulationSettings, load_simulation_config
from models.telemetry import (
    DroneStatus,
    DroneRole,
    DroneTelemetry,
    MeshTopology,
    GSMPoint,
    POIEstimate,
    SimulationStats,
    MissionSnapshot,
)
from models.commands import SimulationConfig


class DroneAgent:
    """Internal state machine and kinematic model of an individual UAV node."""

    def __init__(
        self,
        drone_id: str,
        callsign: str,
        initial_pos: LocalPoint3D,
        waypoints: List[Waypoint],
        speed_mps: float = 12.0,
        lane_idx: int = 0,
        arrival_radius_m: float = 6.0,
        battery_drain_base_rate: float = 0.015,
        battery_drain_speed_factor: float = 0.012,
        battery_low_threshold: float = 20.0,
        gcs_pos: Optional[LocalPoint3D] = None,
    ):
        self.id = drone_id
        self.callsign = callsign
        self.pos = initial_pos
        self.waypoints = waypoints
        self._original_waypoints = list(waypoints)  # backup for resume after RTL
        self.current_wp_idx = 0
        self.speed_mps = speed_mps
        self.heading_deg = 0.0
        self.battery_pct = 100.0
        self.status = DroneStatus.SEARCHING
        self.role = DroneRole.SEARCHER
        self.is_gateway = False
        self.packets_sniffed = 0
        self.lane_idx = lane_idx
        self.arrival_radius_m = arrival_radius_m
        self.battery_drain_base_rate = battery_drain_base_rate
        self.battery_drain_speed_factor = battery_drain_speed_factor
        self.battery_low_threshold = battery_low_threshold
        self.gcs_pos = gcs_pos or LocalPoint3D(0.0, 0.0, 0.0)
        self._rtl_triggered = False

    def _estimate_battery_for_rtl(self) -> float:
        """Estimates battery percentage needed to return to GCS with safety margin."""
        dist_to_gcs = self.pos.distance_to(self.gcs_pos)
        time_to_gcs = dist_to_gcs / max(1.0, self.speed_mps)
        drain_rate = self.battery_drain_base_rate + (self.speed_mps / 15.0) * self.battery_drain_speed_factor
        battery_needed = drain_rate * time_to_gcs
        safety_margin = 5.0  # 5% reserve
        return battery_needed + safety_margin

    def _trigger_rtl(self) -> None:
        """Replaces waypoints with a direct return-to-launch route."""
        if self._rtl_triggered:
            return
        self._rtl_triggered = True
        self.status = DroneStatus.RETURNING
        # Set GCS as sole waypoint target
        rtl_wp = Waypoint(self.gcs_pos.x, self.gcs_pos.y, self.pos.z)
        landing_wp = Waypoint(self.gcs_pos.x, self.gcs_pos.y, 0.0)
        self.waypoints = [rtl_wp, landing_wp]
        self.current_wp_idx = 0

    def update(self, dt_sec: float) -> None:
        """Advances kinematic position, updates heading and consumes battery using config values."""
        if not self.waypoints or self.status == DroneStatus.STANDBY:
            return

        target_wp = self.waypoints[self.current_wp_idx]
        new_pos, heading, arrived = DroneKinematics.update_position(
            current_pos=self.pos,
            target_wp=target_wp,
            speed_mps=self.speed_mps,
            dt_sec=dt_sec,
            arrival_radius_m=self.arrival_radius_m,
        )

        self.pos = new_pos
        self.heading_deg = heading
        self.battery_pct = DroneKinematics.calculate_battery_drain(
            self.battery_pct,
            self.speed_mps,
            dt_sec,
            base_rate=self.battery_drain_base_rate,
            speed_factor=self.battery_drain_speed_factor,
        )

        if arrived:
            if self.status == DroneStatus.RETURNING:
                # Arrived at GCS — land and standby
                if self.current_wp_idx >= len(self.waypoints) - 1:
                    self.status = DroneStatus.STANDBY
                    return
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)

        # RTL check: calculate if battery is sufficient to return safely
        if not self._rtl_triggered and self.status not in (DroneStatus.RETURNING, DroneStatus.STANDBY):
            battery_for_rtl = self._estimate_battery_for_rtl()
            if self.battery_pct <= battery_for_rtl or self.battery_pct <= self.battery_low_threshold:
                self._trigger_rtl()


class SimulationEngine:
    """
    Central simulation orchestrator.
    Executes real-time ticks, manages RF environment, P2P mesh, and POI localization.
    """

    def __init__(self, settings: Optional[SimulationSettings] = None):
        # simulation_config.json is the primary configuration source
        self.settings = settings or load_simulation_config("simulation_config.json")
        self.mission_state = "IDLE"  # IDLE, RUNNING, PAUSED
        self.elapsed_time_sec = 0.0

        # Tactical Area & Reference Frame from configuration
        self.origin_lat = self.settings.area.origin_lat
        self.origin_lon = self.settings.area.origin_lon
        self.geo_ref = GeoReference(self.origin_lat, self.origin_lon, self.settings.area.origin_alt)

        half_w = self.settings.area.area_width_m / 2.0
        half_h = self.settings.area.area_height_m / 2.0
        self.bounds = SearchAreaBounds(
            min_x=-half_w,
            max_x=half_w,
            min_y=-half_h,
            max_y=half_h,
        )

        # GCS Ground Station position
        self.gcs_pos = LocalPoint3D(
            x=self.settings.area.gcs_offset_x_m,
            y=self.settings.area.gcs_offset_y_m,
            z=0.0
        )

        # Subsystems wired strictly from configuration
        self.rf_model = LogDistancePathLoss(
            pl_0_dbm=self.settings.rf.pl_0_dbm,
            path_loss_exponent=self.settings.rf.path_loss_exponent,
            shadowing_sigma_db=self.settings.rf.shadowing_sigma_db,
            rx_sensitivity_dbm=self.settings.rf.rx_sensitivity_dbm,
        )
        self.gsm_env = GSMBlackoutEnvironment(
            self.bounds,
            tower_offset_m=self.settings.gsm.tower_offset_m,
            normal_rssi_dbm=self.settings.gsm.normal_rssi_dbm,
            blackout_rssi_dbm=self.settings.gsm.blackout_rssi_dbm,
            blackout_radius_m=self.settings.gsm.blackout_radius_m,
            center_offset_x_m=self.settings.gsm.center_offset_x_m,
            center_offset_y_m=self.settings.gsm.center_offset_y_m,
            tower_offset_x_m=self.settings.gsm.tower_offset_x_m,
            tower_offset_y_m=self.settings.gsm.tower_offset_y_m,
        )
        self.mesh_router = MeshRouter(
            mesh_range_m=self.settings.mesh.mesh_range_m,
            gcs_range_m=self.settings.mesh.gcs_range_m,
            tx_power_dbm=self.settings.mesh.tx_power_dbm,
            sensitivity_dbm=self.settings.mesh.mesh_sensitivity_dbm,
        )
        self.poi_tracker = POITracker(
            path_loss_model=self.rf_model,
            max_history_len=self.settings.estimation.max_history_observations,
            recency_decay_factor=self.settings.estimation.recency_decay_factor,
            base_uncertainty_radius_m=self.settings.estimation.base_uncertainty_radius_m,
            min_uncertainty_radius_m=self.settings.estimation.min_uncertainty_radius_m,
        )

        # Collections
        self.drones: Dict[str, DroneAgent] = {}
        self.emitters: List[GroundEmitter] = []
        self._gsm_grid_cache: List[GSMPoint] = []
        self._coverage_cells: Set[Tuple[int, int]] = set()

        # Initialize environment and default swarm
        self._initialize_swarm()
        self._seed_default_crisis_emitters()
        self._refresh_gsm_grid()

    def _initialize_swarm(self) -> None:
        """Plans Boustrophedon trajectories and initializes UAV agents."""
        self.drones.clear()
        mode = getattr(self.settings.swarm, "planner_mode", "SYNCHRONIZED_FRONT")
        tracks = BoustrophedonPlanner.generate_swarm_tracks(
            bounds=self.bounds,
            num_drones=self.settings.swarm.num_drones,
            lane_spacing_m=self.settings.swarm.lane_spacing_m,
            altitude_m=self.settings.swarm.search_altitude_m,
            gcs_point=self.gcs_pos,
            mesh_range_m=self.settings.mesh.mesh_range_m,
            mode=mode,
        )

        callsigns = self.settings.swarm.callsigns or ["Vulture-1", "Vulture-2", "Vulture-3", "Vulture-4"]

        for i, track in enumerate(tracks):
            drone_id = f"UAV-0{i + 1}"
            callsign = callsigns[i % len(callsigns)]
            initial_pos = LocalPoint3D(self.gcs_pos.x + (i * 25.0), self.gcs_pos.y, self.settings.swarm.search_altitude_m)

            agent = DroneAgent(
                drone_id=drone_id,
                callsign=callsign,
                initial_pos=initial_pos,
                waypoints=track,
                speed_mps=self.settings.swarm.cruise_speed_mps,
                lane_idx=i,
                arrival_radius_m=self.settings.swarm.arrival_radius_m,
                battery_drain_base_rate=self.settings.swarm.battery_drain_base_rate,
                battery_drain_speed_factor=self.settings.swarm.battery_drain_speed_factor,
                battery_low_threshold=self.settings.swarm.battery_low_threshold,
                gcs_pos=self.gcs_pos,
            )
            self.drones[drone_id] = agent

    def _seed_default_crisis_emitters(self) -> None:
        """Seeds realistic ground victims emitting Wi-Fi / LTE probe packets in blackout zone."""
        self.emitters.clear()
        for v in self.settings.victims:
            self.emitters.append(
                GroundEmitter(
                    raw_id=v.mac,
                    pos=LocalPoint3D(v.local_x, v.local_y, 0.0),
                    signal_type=v.signal_type,
                    tx_power_dbm=v.tx_power_dbm,
                    burst_interval_sec=v.burst_interval_sec,
                )
            )

    def _refresh_gsm_grid(self) -> None:
        """Precomputes 2D GSM signal gradient field for the frontend map."""
        self._gsm_grid_cache = self.gsm_env.generate_grid_points(
            geo_ref=self.geo_ref,
            grid_resolution_m=self.settings.gsm.grid_resolution_m,
        )

    def define_boundary(
        self,
        polygon_coords: Optional[List[Tuple[float, float]]] = None,
        bbox: Optional[List[float]] = None,
    ) -> None:
        """
        Reconfigures operational search boundary from GeoJSON / bounding box.
        Recalculates local metric coordinates, flight plans, and GSM environment.
        """
        if bbox and len(bbox) == 4:
            min_lat, min_lon, max_lat, max_lon = bbox
        elif polygon_coords and len(polygon_coords) >= 3:
            min_lat = min(p[0] for p in polygon_coords)
            max_lat = max(p[0] for p in polygon_coords)
            min_lon = min(p[1] for p in polygon_coords)
            max_lon = max(p[1] for p in polygon_coords)
        else:
            return

        # Update reference origin to center of new boundary
        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0
        self.origin_lat = center_lat
        self.origin_lon = center_lon
        self.geo_ref = GeoReference(center_lat, center_lon)

        sw = self.geo_ref.to_local(min_lat, min_lon)
        ne = self.geo_ref.to_local(max_lat, max_lon)

        self.bounds = SearchAreaBounds(
            min_x=sw.x,
            max_x=ne.x,
            min_y=sw.y,
            max_y=ne.y,
        )

        self.gcs_pos = LocalPoint3D(self.bounds.min_x - 50.0, self.bounds.min_y - 50.0, 0.0)
        self.gsm_env = GSMBlackoutEnvironment(
            self.bounds,
            tower_offset_m=self.settings.gsm.tower_offset_m,
            normal_rssi_dbm=self.settings.gsm.normal_rssi_dbm,
            blackout_rssi_dbm=self.settings.gsm.blackout_rssi_dbm,
            blackout_radius_m=self.settings.gsm.blackout_radius_m,
            center_offset_x_m=self.settings.gsm.center_offset_x_m,
            center_offset_y_m=self.settings.gsm.center_offset_y_m,
            tower_offset_x_m=self.settings.gsm.tower_offset_x_m,
            tower_offset_y_m=self.settings.gsm.tower_offset_y_m,
        )
        self._refresh_gsm_grid()
        self._initialize_swarm()

    def inject_poi(
        self,
        lat: float,
        lon: float,
        signal_type: str = "WIFI_PROBE_REQ",
        raw_mac: Optional[str] = None,
        tx_power_dbm: float = 16.0,
    ) -> str:
        """Dynamically inserts a new victim emitter into the active crisis simulation."""
        local_pos = self.geo_ref.to_local(lat, lon, 0.0)
        mac = raw_mac or f"custom:{time.time_ns() & 0xFFFFFF:06x}"
        emitter = GroundEmitter(
            raw_id=mac,
            pos=local_pos,
            signal_type=signal_type,
            tx_power_dbm=tx_power_dbm,
            burst_interval_sec=4.0,
        )
        self.emitters.append(emitter)
        return emitter.anonymized_id

    def reload_config(self) -> None:
        """Dynamically reloads simulation_config.json into all subsystems."""
        try:
            self.settings = load_simulation_config("simulation_config.json")
            # Update mesh router parameters
            self.mesh_router.mesh_range = self.settings.mesh.mesh_range_m
            self.mesh_router.gcs_range = self.settings.mesh.gcs_range_m
            self.mesh_router.tx_power = self.settings.mesh.tx_power_dbm
            self.mesh_router.sensitivity = self.settings.mesh.mesh_sensitivity_dbm

            # Update RF propagation model
            self.rf_model.pl_0 = self.settings.rf.pl_0_dbm
            self.rf_model.n = self.settings.rf.path_loss_exponent
            self.rf_model.sigma = self.settings.rf.shadowing_sigma_db
            self.rf_model.sensitivity = self.settings.rf.rx_sensitivity_dbm

            # Update POI estimator
            self.poi_tracker.recency_decay_factor = self.settings.estimation.recency_decay_factor
            self.poi_tracker.base_uncertainty = self.settings.estimation.base_uncertainty_radius_m
            self.poi_tracker.min_uncertainty = self.settings.estimation.min_uncertainty_radius_m

            # Update drone speeds
            for agent in self.drones.values():
                agent.speed_mps = self.settings.swarm.cruise_speed_mps
        except Exception as e:
            pass

    # ------------------ Simulation Loop ------------------

    def step(self, dt_sec: float = 1.0) -> MissionSnapshot:
        """
        Executes one discrete simulation step:
        1. Kinematic UAV flight update.
        2. Ground victim RF bursts & interception checks.
        3. Multilateration & uncertainty circle updates.
        4. Mesh topology, link quality & gateway election.
        5. Snapshot generation.
        """
        # Hot-reload config if simulation_config.json changed on disk
        cfg_file = "simulation_config.json"
        if os.path.exists(cfg_file):
            try:
                mtime = os.path.getmtime(cfg_file)
                if not hasattr(self, "_last_config_mtime"):
                    self._last_config_mtime = mtime
                elif mtime > self._last_config_mtime:
                    self._last_config_mtime = mtime
                    self.reload_config()
            except Exception:
                pass

        if self.mission_state == "RUNNING":
            self.elapsed_time_sec += dt_sec

            # 1. Update UAV flight kinematics
            # BUG-7 fix: coverage grid resolution derived from lane spacing
            coverage_cell_size = max(50.0, self.settings.swarm.lane_spacing_m * 0.8)
            for agent in self.drones.values():
                agent.update(dt_sec)
                # Track search coverage cell (resolution tied to lane spacing)
                cell_x = int(agent.pos.x // coverage_cell_size)
                cell_y = int(agent.pos.y // coverage_cell_size)
                self._coverage_cells.add((cell_x, cell_y))

            # 2. Process RF beacon bursts from ground victims
            for emitter in self.emitters:
                burst_triggered = emitter.tick(dt_sec)
                if not burst_triggered:
                    continue

                # Check which drones intercept this packet
                for agent in self.drones.values():
                    dist_3d = agent.pos.distance_to(emitter.pos)
                    rssi = self.rf_model.compute_rssi(
                        distance_m=dist_3d,
                        tx_power_dbm=emitter.tx_power,
                        add_shadowing_noise=True,
                    )

                    if self.rf_model.is_detectable(rssi):
                        agent.packets_sniffed += 1
                        self.poi_tracker.record_detection(
                            anonymized_id=emitter.anonymized_id,
                            signal_type=emitter.signal_type,
                            drone_id=agent.id,
                            drone_pos=agent.pos,
                            rssi_dbm=rssi,
                            tx_power_dbm=emitter.tx_power,
                            sim_time=self.elapsed_time_sec,
                        )

        # 3. Dynamic P2P Mesh Topology & Gateway Election
        drone_positions = {drone_id: agent.pos for drone_id, agent in self.drones.items()}
        mesh_topology = self.mesh_router.compute_topology(drone_positions, self.gcs_pos)

        # Update UAV role & gateway flag from mesh router
        for agent in self.drones.values():
            is_gw = (agent.id == mesh_topology.gateway_id)
            agent.is_gateway = is_gw
            if is_gw:
                agent.role = DroneRole.GATEWAY
            else:
                agent.role = DroneRole.SEARCHER

        # Populate GPS coordinates on mesh nodes for frontend
        for node in mesh_topology.nodes:
            if node.type == "GCS":
                gcs_geo = self.geo_ref.to_geo(self.gcs_pos.x, self.gcs_pos.y)
                node.lat = round(gcs_geo.lat, 6)
                node.lon = round(gcs_geo.lon, 6)
            elif node.id in self.drones:
                d_pos = self.drones[node.id].pos
                d_geo = self.geo_ref.to_geo(d_pos.x, d_pos.y, d_pos.z)
                node.lat = round(d_geo.lat, 6)
                node.lon = round(d_geo.lon, 6)

        # 4. Generate Telemetry Models
        drone_telemetries: List[DroneTelemetry] = []
        total_packets = 0

        for agent in self.drones.values():
            geo = self.geo_ref.to_geo(agent.pos.x, agent.pos.y, agent.pos.z)
            total_packets += agent.packets_sniffed

            planned_coords = [
                [round(self.geo_ref.to_geo(wp.x, wp.y, wp.z).lat, 6),
                 round(self.geo_ref.to_geo(wp.x, wp.y, wp.z).lon, 6)]
                for wp in agent.waypoints
            ]

            drone_telemetries.append(
                DroneTelemetry(
                    id=agent.id,
                    callsign=agent.callsign,
                    lat=round(geo.lat, 6),
                    lon=round(geo.lon, 6),
                    alt_m=round(agent.pos.z, 1),
                    heading_deg=round(agent.heading_deg, 1),
                    speed_mps=round(agent.speed_mps, 1),
                    battery_pct=agent.battery_pct,
                    status=agent.status,
                    role=agent.role,
                    is_gateway=agent.is_gateway,
                    packets_sniffed=agent.packets_sniffed,
                    current_lane=agent.lane_idx,
                    planned_path=planned_coords,
                )
            )

        # 5. POI Estimates
        poi_estimates = self.poi_tracker.get_all_estimates(self.geo_ref, current_sim_time=self.elapsed_time_sec)

        # 6. Area Coverage Statistics
        total_area = self.bounds.width * self.bounds.height
        # BUG-7 fix: coverage grid resolution consistent with tracking cells
        coverage_cell_size = max(50.0, self.settings.swarm.lane_spacing_m * 0.8)
        total_grid_cells = max(1, int((self.bounds.width / coverage_cell_size) * (self.bounds.height / coverage_cell_size)))
        covered_pct = min(100.0, round((len(self._coverage_cells) / total_grid_cells) * 100.0, 1))

        stats = SimulationStats(
            elapsed_time_sec=round(self.elapsed_time_sec, 1),
            active_drones=len(self.drones),
            total_search_area_sqm=round(total_area, 0),
            area_covered_pct=covered_pct,
            packets_intercepted=total_packets,
            pois_discovered=len(poi_estimates),
            gcs_online=mesh_topology.gcs_connected,
            mesh_links_count=len(mesh_topology.edges),
        )

        # 7. Boundary Polygon in WGS84 for Map rendering
        b_sw = self.geo_ref.to_geo(self.bounds.min_x, self.bounds.min_y)
        b_se = self.geo_ref.to_geo(self.bounds.max_x, self.bounds.min_y)
        b_ne = self.geo_ref.to_geo(self.bounds.max_x, self.bounds.max_y)
        b_nw = self.geo_ref.to_geo(self.bounds.min_x, self.bounds.max_y)
        boundary_wgs84 = [
            [round(b_sw.lat, 6), round(b_sw.lon, 6)],
            [round(b_se.lat, 6), round(b_se.lon, 6)],
            [round(b_ne.lat, 6), round(b_ne.lon, 6)],
            [round(b_nw.lat, 6), round(b_nw.lon, 6)],
            [round(b_sw.lat, 6), round(b_sw.lon, 6)],
        ]

        gcs_geo = self.geo_ref.to_geo(self.gcs_pos.x, self.gcs_pos.y)
        bts_geo = self.geo_ref.to_geo(self.gsm_env.bts_x, self.gsm_env.bts_y)
        crisis_geo = self.geo_ref.to_geo(self.gsm_env.crisis_cx, self.gsm_env.crisis_cy)

        return MissionSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mission_state=self.mission_state,
            drones=drone_telemetries,
            mesh=mesh_topology,
            gsm_grid=self._gsm_grid_cache,
            pois=poi_estimates,
            stats=stats,
            boundary=boundary_wgs84,
            gcs_position={"lat": round(gcs_geo.lat, 6), "lon": round(gcs_geo.lon, 6)},
            gsm_tower_position={"lat": round(bts_geo.lat, 6), "lon": round(bts_geo.lon, 6)},
            gsm_crisis_center={
                "lat": round(crisis_geo.lat, 6),
                "lon": round(crisis_geo.lon, 6),
                "radius_m": round(self.gsm_env.crisis_radius, 1),
            },
        )

    # ------------------ Control Operations ------------------

    def start(self) -> None:
        self.mission_state = "RUNNING"
        for agent in self.drones.values():
            agent.status = DroneStatus.SEARCHING

    def pause(self) -> None:
        self.mission_state = "PAUSED"
        for agent in self.drones.values():
            agent.status = DroneStatus.HOVERING

    def resume(self) -> None:
        self.start()

    def reset(self) -> None:
        self.mission_state = "IDLE"
        self.elapsed_time_sec = 0.0
        self._coverage_cells.clear()
        self.poi_tracker.clear()
        # Always reload primary simulation_config.json on reset
        self.reload_config()
        self._initialize_swarm()
        self._seed_default_crisis_emitters()
        self._refresh_gsm_grid()
