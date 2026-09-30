"""
OutOfBlack - Central Swarm Simulation Engine.
Coordinates UAV kinematics, RF propagation, Mesh P2P routing, GSM blackout, and POI localization.
"""

from __future__ import annotations
import os
import math
import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set

logger = logging.getLogger("OutOfBlack")

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
    GSMSector,
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
        battery_drain_base_rate: float = 0.020,
        battery_drain_speed_factor: float = 0.015,
        drain_multiplier: float = 1.0,
        battery_low_threshold: float = 20.0,
        gcs_pos: Optional[LocalPoint3D] = None,
        launch_pos: Optional[LocalPoint3D] = None,
    ):
        self.id = drone_id
        self.callsign = callsign
        self.pos = initial_pos
        self.launch_pos = launch_pos or initial_pos
        self.waypoints = waypoints
        self._original_waypoints = list(waypoints)  # backup for resume after RTL
        self._cached_planned_path: Optional[List[List[float]]] = None  # geo cache
        self.current_wp_idx = 0
        self.base_cruise_speed_mps = speed_mps
        self.sprint_speed_mps = round(speed_mps * 1.35, 1)
        self.rtl_speed_mps = round(speed_mps * 1.08, 1)
        self.speed_mps = speed_mps
        self.heading_deg = 0.0
        self.battery_pct = 100.0
        self.status = DroneStatus.STANDBY
        self.role = DroneRole.SEARCHER
        self.is_gateway = False
        self.packets_sniffed = 0
        self.lane_idx = lane_idx
        self.arrival_radius_m = arrival_radius_m
        self.battery_drain_base_rate = battery_drain_base_rate
        self.battery_drain_speed_factor = battery_drain_speed_factor
        self.drain_multiplier = drain_multiplier
        self.current_drain_rate = 0.0
        self.battery_low_threshold = battery_low_threshold
        self.gcs_pos = gcs_pos or LocalPoint3D(0.0, 0.0, 0.0)
        self._rtl_triggered = False
        self.needs_battery_swap = False
        self.battery_swapped = False

        # POI Signal Inspection & Hover Mode
        self.target_poi_id: Optional[str] = None
        self._saved_waypoints: Optional[List[Waypoint]] = None
        self._saved_wp_idx: int = 0
        self._hover_time_sec: float = 0.0
        self._max_hover_time_sec: Optional[float] = None
        self._breakoff_pos: Optional[LocalPoint3D] = None
        self._resuming_to_breakoff: bool = False

    def dispatch_to_poi(
        self,
        poi_id: str,
        target_pos: LocalPoint3D,
        altitude_m: float = 35.0,
        hover_duration_sec: Optional[float] = None,
    ) -> None:
        """Commands drone to break from search track, fly directly to POI, and hover/inspect."""
        if not self._saved_waypoints:
            self._saved_waypoints = list(self.waypoints)
            self._saved_wp_idx = self.current_wp_idx

        self.target_poi_id = poi_id
        self.status = DroneStatus.TRANSIT
        self._hover_time_sec = 0.0
        self._max_hover_time_sec = hover_duration_sec

        # Plan inspection approach and tight hover orbit directly over target
        r = 20.0
        loiter_wps = [
            Waypoint(target_pos.x, target_pos.y, altitude_m),
            Waypoint(target_pos.x + r, target_pos.y, altitude_m),
            Waypoint(target_pos.x, target_pos.y + r, altitude_m, is_turn=True),
            Waypoint(target_pos.x - r, target_pos.y, altitude_m, is_turn=True),
            Waypoint(target_pos.x, target_pos.y - r, altitude_m, is_turn=True),
            Waypoint(target_pos.x + r, target_pos.y, altitude_m, is_turn=True),
        ]
        self.waypoints = loiter_wps
        self.current_wp_idx = 0
        self._cached_planned_path = None  # invalidate geo cache

    def resume_search(self) -> None:
        """Resumes original Boustrophedon sweep trajectory."""
        if self._saved_waypoints:
            self.waypoints = list(self._saved_waypoints)
            self.current_wp_idx = min(self._saved_wp_idx, len(self.waypoints) - 1)
            self._saved_waypoints = None
            self._cached_planned_path = None  # invalidate geo cache
        self.target_poi_id = None
        self.status = DroneStatus.SEARCHING
        self._max_hover_time_sec = None

    def _estimate_battery_for_rtl(self) -> float:
        """Estimates battery percentage needed to return to launch base with safety margin."""
        home_pos = self.launch_pos or self.gcs_pos
        dist_to_home = self.pos.distance_to(home_pos)
        speed = getattr(self, "rtl_speed_mps", self.speed_mps)
        time_to_home = dist_to_home / max(1.0, speed)
        drain_rate = (self.battery_drain_base_rate + self.battery_drain_speed_factor) * getattr(self, "drain_multiplier", 1.0)
        battery_needed = drain_rate * time_to_home
        safety_margin = 5.0  # 5% reserve
        return battery_needed + safety_margin

    def _trigger_rtl(self) -> None:
        """Replaces waypoints with a direct return-to-launch route."""
        if self._rtl_triggered:
            return
        self._rtl_triggered = True
        self.target_poi_id = None
        self.status = DroneStatus.RETURNING
        home_pos = self.launch_pos or self.gcs_pos
        # Save original search waypoints and index so drone can resume after landing and battery swap
        if not self._saved_waypoints:
            self._saved_waypoints = list(self._original_waypoints or self.waypoints)
            self._saved_wp_idx = self.current_wp_idx
        # Preserve the exact 3D coordinates where the mission sweep was interrupted
        self._breakoff_pos = LocalPoint3D(self.pos.x, self.pos.y, self.pos.z)
        self._resuming_to_breakoff = False
        rtl_wp = Waypoint(home_pos.x, home_pos.y, self.pos.z)
        landing_wp = Waypoint(home_pos.x, home_pos.y, 0.0)
        self.waypoints = [rtl_wp, landing_wp]
        self.current_wp_idx = 0
        self._cached_planned_path = None  # invalidate geo cache

    def relaunch(self, target_altitude_m: float) -> None:
        """Relaunches drone from base after servicing, routing it back to break-off point if applicable."""
        if getattr(self, "_breakoff_pos", None):
            # Return to exact point where previous sweep was interrupted
            breakoff_wp = Waypoint(self._breakoff_pos.x, self._breakoff_pos.y, target_altitude_m)
            remaining_wps = []
            if self._saved_waypoints:
                remaining_wps = list(self._saved_waypoints[getattr(self, "_saved_wp_idx", 0):])
            if not remaining_wps and self._original_waypoints:
                remaining_wps = list(self._original_waypoints)
            self.waypoints = [breakoff_wp] + (remaining_wps or [breakoff_wp])
            self.current_wp_idx = 0
            self.status = DroneStatus.TRANSIT
            self._resuming_to_breakoff = True
            self._saved_waypoints = None
        elif self._saved_waypoints:
            self.waypoints = list(self._saved_waypoints)
            self.current_wp_idx = min(getattr(self, "_saved_wp_idx", 0), len(self.waypoints) - 1)
            self._saved_waypoints = None
            self.status = DroneStatus.SEARCHING
            self._resuming_to_breakoff = False
        elif self._original_waypoints:
            self.waypoints = list(self._original_waypoints)
            self.current_wp_idx = 0
            self.status = DroneStatus.SEARCHING
            self._resuming_to_breakoff = False

        self.pos = LocalPoint3D(self.pos.x, self.pos.y, target_altitude_m)
        self.needs_battery_swap = False
        self.battery_swapped = False
        self._rtl_triggered = False
        self._cached_planned_path = None

    def update(self, dt_sec: float) -> None:
        """Advances kinematic position, updates heading and consumes battery using speed-dependent aerodynamic models."""
        if not self.waypoints or self.status == DroneStatus.STANDBY:
            self.current_drain_rate = 0.0
            return

        is_hovering = (self.status == DroneStatus.HOVERING)

        # Dynamic operational speed based on flight state
        if is_hovering:
            self.speed_mps = 0.0
        elif self.status == DroneStatus.TRANSIT:
            # High-speed sprint when dispatched to inspect an urgent victim POI
            self.speed_mps = getattr(self, "sprint_speed_mps", round(self.base_cruise_speed_mps * 1.35, 1))
        elif self.status == DroneStatus.RETURNING:
            # Optimal energy return-to-launch speed
            self.speed_mps = getattr(self, "rtl_speed_mps", round(self.base_cruise_speed_mps * 1.08, 1))
        else:
            # SEARCHING: individual calibrated cruise speed with corner deceleration in turns
            target_wp = self.waypoints[self.current_wp_idx]
            if target_wp.is_turn:
                self.speed_mps = round(self.base_cruise_speed_mps * 0.75, 1)
            else:
                self.speed_mps = self.base_cruise_speed_mps

        target_wp = self.waypoints[self.current_wp_idx]
        new_pos, heading, arrived = DroneKinematics.update_position(
            current_pos=self.pos,
            target_wp=target_wp,
            speed_mps=max(0.5, self.speed_mps) if not is_hovering else 0.0,
            dt_sec=dt_sec,
            arrival_radius_m=self.arrival_radius_m,
        )

        self.pos = new_pos
        self.heading_deg = heading
        self.battery_pct, self.current_drain_rate = DroneKinematics.calculate_battery_drain(
            current_battery=self.battery_pct,
            speed_mps=self.speed_mps,
            dt_sec=dt_sec,
            base_rate=self.battery_drain_base_rate,
            speed_factor=self.battery_drain_speed_factor,
            drain_multiplier=getattr(self, "drain_multiplier", 1.0),
            is_hovering=is_hovering,
            is_gateway=self.is_gateway,
            reference_speed_mps=getattr(self, "base_cruise_speed_mps", 18.0),
        )

        if arrived:
            if self.status == DroneStatus.RETURNING:
                # Arrived at launch base / GCS — touchdown, enter standby, await battery swap
                if self.current_wp_idx >= len(self.waypoints) - 1:
                    self.status = DroneStatus.STANDBY
                    self.speed_mps = 0.0
                    self.pos = LocalPoint3D(self.pos.x, self.pos.y, 0.0)
                    self.needs_battery_swap = True
                    self.battery_swapped = False
                    return
            elif self.status == DroneStatus.TRANSIT and getattr(self, "_resuming_to_breakoff", False):
                # Arrived at break-off position where mission was interrupted!
                # Switch to SEARCHING mode and resume search corridor
                self.status = DroneStatus.SEARCHING
                self._resuming_to_breakoff = False
                self._breakoff_pos = None
            elif self.status == DroneStatus.TRANSIT and self.target_poi_id:
                # Arrived at POI target — switch to HOVERING inspection mode
                self.status = DroneStatus.HOVERING
            elif self.current_wp_idx >= len(self.waypoints) - 1:
                # Reached final planned waypoint
                target = self.waypoints[self.current_wp_idx]
                if target.z <= 1.0 or self.battery_pct <= self.battery_low_threshold + 5.0:
                    self.status = DroneStatus.STANDBY
                    return
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)

        # In HOVERING mode, track duration if max_hover_time_sec is set
        if self.status == DroneStatus.HOVERING:
            self._hover_time_sec += dt_sec
            if self._max_hover_time_sec and self._hover_time_sec >= self._max_hover_time_sec:
                self.resume_search()

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
        self.gsm_sectors: Dict[str, dict] = {}

        # Initialize environment and default swarm
        self._initialize_swarm()
        self._seed_default_crisis_emitters()
        self._refresh_gsm_grid()
        self._init_gsm_sectors()

    def _initialize_swarm(self) -> None:
        """Plans Boustrophedon trajectories and initializes UAV agents with launch-origin and battery awareness."""
        self.drones.clear()
        mode = getattr(self.settings.swarm, "planner_mode", "SYNCHRONIZED_FRONT")
        num_drones = self.settings.swarm.num_drones
        callsigns = self.settings.swarm.callsigns or [f"Vulture-{i+1}" for i in range(num_drones)]

        # Determine individual takeoff launch points per drone
        launch_points: List[LocalPoint3D] = []
        cfg_launch = getattr(self.settings.swarm, "launch_offsets_m", None)

        for i in range(num_drones):
            if cfg_launch and i < len(cfg_launch):
                pt = cfg_launch[i]
                if "lat" in pt and "lon" in pt:
                    lp = self.geo_ref.to_local(pt["lat"], pt["lon"], self.settings.swarm.search_altitude_m)
                else:
                    lp = LocalPoint3D(
                        x=pt.get("x", self.gcs_pos.x + i * 25.0),
                        y=pt.get("y", self.gcs_pos.y),
                        z=self.settings.swarm.search_altitude_m,
                    )
            else:
                lp = LocalPoint3D(
                    x=self.gcs_pos.x + (i * 25.0),
                    y=self.gcs_pos.y,
                    z=self.settings.swarm.search_altitude_m,
                )
            launch_points.append(lp)

        tracks = BoustrophedonPlanner.generate_swarm_tracks(
            bounds=self.bounds,
            num_drones=num_drones,
            lane_spacing_m=self.settings.swarm.lane_spacing_m,
            altitude_m=self.settings.swarm.search_altitude_m,
            gcs_point=self.gcs_pos,
            mesh_range_m=self.settings.mesh.mesh_range_m,
            mode=mode,
            launch_points=launch_points,
            cruise_speed_mps=self.settings.swarm.cruise_speed_mps,
            battery_drain_base_rate=self.settings.swarm.battery_drain_base_rate,
            battery_drain_speed_factor=self.settings.swarm.battery_drain_speed_factor,
            battery_low_threshold=self.settings.swarm.battery_low_threshold,
            gcs_range_m=self.settings.mesh.gcs_range_m,
            max_sensor_range_m=getattr(self.settings.swarm, "max_sensor_range_m", 250.0),
        )

        base_cruise = self.settings.swarm.cruise_speed_mps
        # Heterogeneous speed variations per drone reflecting payload, aerodynamics, and role
        speed_variations = [0.92, 1.06, 1.18, 0.96, 1.12, 1.22, 1.02, 1.14]
        # Heterogeneous battery consumption multipliers reflecting payload sensors, battery health, and aerodynamics
        drain_multipliers = [1.25, 1.15, 0.82, 1.02, 1.20, 0.88, 1.10, 0.95]

        for i, track in enumerate(tracks):
            drone_id = f"UAV-0{i + 1}"
            callsign = callsigns[i % len(callsigns)]
            initial_pos = LocalPoint3D(launch_points[i].x, launch_points[i].y, self.settings.swarm.search_altitude_m)
            var_factor = speed_variations[i % len(speed_variations)]
            assigned_speed = round(base_cruise * var_factor, 1)
            assigned_drain = drain_multipliers[i % len(drain_multipliers)]

            agent = DroneAgent(
                drone_id=drone_id,
                callsign=callsign,
                initial_pos=initial_pos,
                waypoints=track,
                speed_mps=assigned_speed,
                lane_idx=i,
                arrival_radius_m=self.settings.swarm.arrival_radius_m,
                battery_drain_base_rate=self.settings.swarm.battery_drain_base_rate,
                battery_drain_speed_factor=self.settings.swarm.battery_drain_speed_factor,
                drain_multiplier=assigned_drain,
                battery_low_threshold=self.settings.swarm.battery_low_threshold,
                gcs_pos=self.gcs_pos,
                launch_pos=launch_points[i],
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

    def _init_gsm_sectors(self) -> None:
        """
        Partitions the operational search area into a discrete tactical reconnaissance grid (e.g. A1, B2).
        Initially, all sectors are unvisited (Fog of War) until a drone flies over them and sniffs GSM.
        """
        self.gsm_sectors.clear()
        w = max(100.0, self.bounds.max_x - self.bounds.min_x)
        h = max(100.0, self.bounds.max_y - self.bounds.min_y)

        # Dynamic grid dimensioning: ~600m - 750m per sector cell
        ncols = max(3, min(8, int(round(w / 650.0))))
        nrows = max(3, min(8, int(round(h / 650.0))))
        dx = w / ncols
        dy = h / nrows

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        for r in range(nrows):
            row_letter = letters[r % len(letters)]
            # North is max_y, South is min_y
            y_top = self.bounds.max_y - (r * dy)
            y_bottom = self.bounds.max_y - ((r + 1) * dy)

            for c in range(ncols):
                col_num = c + 1
                sec_id = f"{row_letter}{col_num}"
                x_left = self.bounds.min_x + (c * dx)
                x_right = self.bounds.min_x + ((c + 1) * dx)

                # Geographic corners: SW, SE, NE, NW, SW
                sw_geo = self.geo_ref.to_geo(x_left, y_bottom)
                se_geo = self.geo_ref.to_geo(x_right, y_bottom)
                ne_geo = self.geo_ref.to_geo(x_right, y_top)
                nw_geo = self.geo_ref.to_geo(x_left, y_top)

                bounds_geo = [
                    [round(sw_geo.lat, 6), round(sw_geo.lon, 6)],
                    [round(se_geo.lat, 6), round(se_geo.lon, 6)],
                    [round(ne_geo.lat, 6), round(ne_geo.lon, 6)],
                    [round(nw_geo.lat, 6), round(nw_geo.lon, 6)],
                    [round(sw_geo.lat, 6), round(sw_geo.lon, 6)],
                ]

                cx = (x_left + x_right) / 2.0
                cy = (y_top + y_bottom) / 2.0
                c_geo = self.geo_ref.to_geo(cx, cy)

                self.gsm_sectors[sec_id] = {
                    "id": sec_id,
                    "name": f"Sektor {sec_id}",
                    "bounds": bounds_geo,
                    "center_lat": round(c_geo.lat, 6),
                    "center_lon": round(c_geo.lon, 6),
                    "local_x0": x_left,
                    "local_x1": x_right,
                    "local_y0": y_bottom,
                    "local_y1": y_top,
                    "center_x": cx,
                    "center_y": cy,
                    "surveyed": False,
                    "status": "UNKNOWN",
                    "avg_rssi_dbm": None,
                    "surveyed_by": None,
                    "surveyed_time_sec": None,
                }

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
        self._init_gsm_sectors()
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

    def inspect_poi(
        self,
        anonymized_id: str,
        drone_id: Optional[str] = None,
        altitude_m: float = 35.0,
        hover_duration_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Operator command: dispatches a drone to hover directly over a detected POI
        to inspect and verify the victim's RF signal.
        """
        # Find POI estimate or emitter
        estimate = self.poi_tracker.estimate_poi(anonymized_id, self.geo_ref, self.elapsed_time_sec)
        target_pos = None
        if estimate:
            target_pos = self.geo_ref.to_local(estimate.est_lat, estimate.est_lon, 0.0)
        else:
            emitter = next((e for e in self.emitters if e.anonymized_id == anonymized_id), None)
            if emitter:
                target_pos = emitter.pos

        if not target_pos:
            return {"status": "ERROR", "success": False, "message": f"POI {anonymized_id} not found."}

        # Select drone: specific ID or closest available search drone
        agent = None
        if drone_id and drone_id in self.drones:
            agent = self.drones[drone_id]
        else:
            candidates = [
                d for d in self.drones.values()
                if d.status not in (DroneStatus.RETURNING, DroneStatus.STANDBY)
            ]
            if not candidates:
                return {"status": "ERROR", "success": False, "message": "No active drones available for inspection."}
            agent = min(candidates, key=lambda d: d.pos.distance_to(target_pos))

        agent.dispatch_to_poi(
            poi_id=anonymized_id,
            target_pos=target_pos,
            altitude_m=altitude_m,
            hover_duration_sec=hover_duration_sec,
        )

        target_geo = self.geo_ref.to_geo(target_pos.x, target_pos.y)
        return {
            "status": "SUCCESS",
            "success": True,
            "message": f"Dron {agent.callsign} ({agent.id}) skierowany do zbadania sygnału {anonymized_id} (tryb zawisu/hover).",
            "drone_id": agent.id,
            "callsign": agent.callsign,
            "anonymized_id": anonymized_id,
            "target_lat": round(target_geo.lat, 6),
            "target_lon": round(target_geo.lon, 6),
        }

    def resume_search(self, drone_id: Optional[str] = None) -> Dict[str, Any]:
        """Operator command: returns inspecting drone(s) to original search patrol."""
        resumed = []
        if drone_id and drone_id in self.drones:
            self.drones[drone_id].resume_search()
            resumed.append(drone_id)
        else:
            for agent in self.drones.values():
                if agent.target_poi_id:
                    agent.resume_search()
                    resumed.append(agent.id)

        return {
            "status": "SUCCESS",
            "success": True,
            "message": f"Drony wznowiły standardowy patrol: {', '.join(resumed) if resumed else 'wszystkie'}.",
            "resumed_drones": resumed,
        }


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

            # Update drone speeds with individual calibrated variations
            base_cruise = self.settings.swarm.cruise_speed_mps
            speed_variations = [0.92, 1.06, 1.18, 0.96, 1.12, 1.22, 1.02, 1.14]
            drain_multipliers = [1.25, 1.15, 0.82, 1.02, 1.20, 0.88, 1.10, 0.95]
            for i, agent in enumerate(self.drones.values()):
                var_factor = speed_variations[i % len(speed_variations)]
                agent.drain_multiplier = drain_multipliers[i % len(drain_multipliers)]
                agent.battery_drain_base_rate = self.settings.swarm.battery_drain_base_rate
                agent.battery_drain_speed_factor = self.settings.swarm.battery_drain_speed_factor
                agent.base_cruise_speed_mps = round(base_cruise * var_factor, 1)
                agent.sprint_speed_mps = round(agent.base_cruise_speed_mps * 1.35, 1)
                agent.rtl_speed_mps = round(agent.base_cruise_speed_mps * 1.08, 1)
                if agent.status == DroneStatus.HOVERING:
                    agent.speed_mps = 0.0
                elif agent.status == DroneStatus.TRANSIT:
                    agent.speed_mps = agent.sprint_speed_mps
                elif agent.status == DroneStatus.RETURNING:
                    agent.speed_mps = agent.rtl_speed_mps
                else:
                    agent.speed_mps = agent.base_cruise_speed_mps

            # Update GSM environment and refresh cached grid & sectors
            self.gsm_env.normal_rssi = self.settings.gsm.normal_rssi_dbm
            self.gsm_env.blackout_rssi = self.settings.gsm.blackout_rssi_dbm
            self.gsm_env.crisis_radius = self.settings.gsm.blackout_radius_m
            self._refresh_gsm_grid()
            self._init_gsm_sectors()
        except Exception as e:
            logger.error(f"Failed to reload simulation config: {e}", exc_info=True)

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
        if self.mission_state in ("RUNNING", "RETURNING"):
            self.elapsed_time_sec += dt_sec

            # 1. Update UAV flight kinematics
            # BUG-7 fix: coverage grid resolution derived from lane spacing
            coverage_cell_size = max(50.0, min(120.0, self.settings.swarm.lane_spacing_m * 0.6))
            sensor_radius = max(
                getattr(self.settings.swarm, "max_sensor_range_m", 250.0),
                self.settings.swarm.lane_spacing_m * 0.75,
            )

            for agent in self.drones.values():
                agent.update(dt_sec)
                # Track search coverage cells within sensor detection footprint (only when airborne)
                if agent.status != DroneStatus.STANDBY and agent.pos.z > 5.0:
                    r_steps = int(math.ceil(sensor_radius / coverage_cell_size))
                    base_cx = int(agent.pos.x // coverage_cell_size)
                    base_cy = int(agent.pos.y // coverage_cell_size)
                    for dx in range(-r_steps, r_steps + 1):
                        for dy in range(-r_steps, r_steps + 1):
                            cx = (base_cx + dx + 0.5) * coverage_cell_size
                            cy = (base_cy + dy + 0.5) * coverage_cell_size
                            if (
                                self.bounds.min_x <= cx <= self.bounds.max_x
                                and self.bounds.min_y <= cy <= self.bounds.max_y
                                and math.hypot(cx - agent.pos.x, cy - agent.pos.y) <= sensor_radius
                            ):
                                self._coverage_cells.add((base_cx + dx, base_cy + dy))

                # 1b. GSM RF Reconnaissance / Sector Blackout Survey
                for sec in self.gsm_sectors.values():
                    if (
                        (sec["local_x0"] - sensor_radius) <= agent.pos.x <= (sec["local_x1"] + sensor_radius)
                        and (sec["local_y0"] - sensor_radius) <= agent.pos.y <= (sec["local_y1"] + sensor_radius)
                    ):
                        if not sec["surveyed"]:
                            sec["surveyed"] = True
                            sec["surveyed_by"] = agent.callsign
                            sec["surveyed_time_sec"] = round(self.elapsed_time_sec, 1)

                            # Multi-point RF sampling across the sector for accurate blackout classification
                            samples = [
                                self.gsm_env.get_gsm_rssi(sec["center_x"], sec["center_y"]),
                                self.gsm_env.get_gsm_rssi(sec["local_x0"] * 0.75 + sec["local_x1"] * 0.25, sec["local_y0"] * 0.75 + sec["local_y1"] * 0.25),
                                self.gsm_env.get_gsm_rssi(sec["local_x0"] * 0.25 + sec["local_x1"] * 0.75, sec["local_y0"] * 0.75 + sec["local_y1"] * 0.25),
                                self.gsm_env.get_gsm_rssi(sec["local_x0"] * 0.75 + sec["local_x1"] * 0.25, sec["local_y0"] * 0.25 + sec["local_y1"] * 0.75),
                                self.gsm_env.get_gsm_rssi(sec["local_x0"] * 0.25 + sec["local_x1"] * 0.75, sec["local_y0"] * 0.25 + sec["local_y1"] * 0.75),
                            ]
                            avg_rssi = sum(samples) / len(samples)
                            min_rssi = min(samples)
                            sec["avg_rssi_dbm"] = round(avg_rssi, 1)
                            if min_rssi <= -100.0 or avg_rssi <= -98.0:
                                sec["status"] = "BLACKOUT"
                            elif avg_rssi < -85.0:
                                sec["status"] = "DEGRADED"
                            else:
                                sec["status"] = "NORMAL"

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

            if self.mission_state == "RETURNING":
                all_landed = all(d.status == DroneStatus.STANDBY for d in self.drones.values())
                if all_landed:
                    self.mission_state = "IDLE"

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

            # Use cached geo coords for planned path — only recompute when waypoints change
            if agent._cached_planned_path is None:
                agent._cached_planned_path = [
                    [round(self.geo_ref.to_geo(wp.x, wp.y, wp.z).lat, 6),
                     round(self.geo_ref.to_geo(wp.x, wp.y, wp.z).lon, 6)]
                    for wp in agent.waypoints
                ]
            planned_coords = agent._cached_planned_path

            drone_telemetries.append(
                DroneTelemetry(
                    id=agent.id,
                    callsign=agent.callsign,
                    lat=round(geo.lat, 6),
                    lon=round(geo.lon, 6),
                    alt_m=round(agent.pos.z, 1),
                    heading_deg=round(agent.heading_deg, 1),
                    speed_mps=round(agent.speed_mps, 1),
                    battery_pct=round(agent.battery_pct, 1),
                    status=agent.status,
                    role=agent.role,
                    is_gateway=agent.is_gateway,
                    packets_sniffed=agent.packets_sniffed,
                    current_lane=agent.lane_idx,
                    planned_path=planned_coords,
                    target_poi_id=agent.target_poi_id,
                    needs_battery_swap=getattr(agent, "needs_battery_swap", False),
                    battery_swapped=getattr(agent, "battery_swapped", False),
                    battery_drain_rate=round(getattr(agent, "current_drain_rate", 0.0), 4),
                )
            )

        # 5. POI Estimates & Inspection Enrichment
        poi_estimates = self.poi_tracker.get_all_estimates(self.geo_ref, current_sim_time=self.elapsed_time_sec)
        inspecting_map = {agent.target_poi_id: agent for agent in self.drones.values() if agent.target_poi_id}
        for poi in poi_estimates:
            if poi.anonymized_id in inspecting_map:
                agent = inspecting_map[poi.anonymized_id]
                poi.is_being_inspected = True
                poi.inspecting_drone_id = agent.callsign
                # When hovering directly over target, signal inspection bonus
                if agent.status == DroneStatus.HOVERING:
                    poi.uncertainty_radius_m = min(poi.uncertainty_radius_m, 12.0)
                    poi.confidence = max(poi.confidence, 0.98)


        # 6. Area Coverage Statistics
        total_area = self.bounds.width * self.bounds.height
        # BUG-7 fix: coverage grid resolution consistent with tracking cells
        coverage_cell_size = max(50.0, min(120.0, self.settings.swarm.lane_spacing_m * 0.6))
        total_grid_cells = max(1, int((self.bounds.width / coverage_cell_size) * (self.bounds.height / coverage_cell_size)))
        covered_pct = min(100.0, round((len(self._coverage_cells) / total_grid_cells) * 100.0, 1))

        total_sectors = len(self.gsm_sectors)
        surveyed_sectors = sum(1 for s in self.gsm_sectors.values() if s["surveyed"])
        blackout_sectors = sum(1 for s in self.gsm_sectors.values() if s["status"] == "BLACKOUT")
        recon_pct = round((surveyed_sectors / total_sectors) * 100.0, 1) if total_sectors > 0 else 0.0

        stats = SimulationStats(
            elapsed_time_sec=round(self.elapsed_time_sec, 1),
            active_drones=len(self.drones),
            total_search_area_sqm=round(total_area, 0),
            area_covered_pct=covered_pct,
            packets_intercepted=total_packets,
            pois_discovered=len(poi_estimates),
            gcs_online=mesh_topology.gcs_connected,
            mesh_links_count=len(mesh_topology.edges),
            gsm_sectors_total=total_sectors,
            gsm_sectors_surveyed=surveyed_sectors,
            gsm_sectors_blackout=blackout_sectors,
            gsm_recon_pct=recon_pct,
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

        # 8. GSM Sectors for Tactical Fog-of-War Map Reconnaissance
        gsm_sectors_list = [
            GSMSector(
                id=s["id"],
                name=s["name"],
                bounds=s["bounds"],
                center_lat=s["center_lat"],
                center_lon=s["center_lon"],
                surveyed=s["surveyed"],
                status=s["status"],
                avg_rssi_dbm=s["avg_rssi_dbm"],
                surveyed_by=s["surveyed_by"],
                surveyed_time_sec=s["surveyed_time_sec"],
            )
            for s in self.gsm_sectors.values()
        ]

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
            gsm_sectors=gsm_sectors_list,
        )

    # ------------------ Control Operations ------------------

    def start(self) -> None:
        self.mission_state = "RUNNING"
        for agent in self.drones.values():
            if agent.status == DroneStatus.STANDBY:
                if agent.battery_pct >= 25.0:
                    agent.relaunch(self.settings.swarm.search_altitude_m)
            elif agent.status not in (DroneStatus.RETURNING, DroneStatus.TRANSIT, DroneStatus.HOVERING):
                agent.status = DroneStatus.SEARCHING

    def abort(self) -> Dict[str, Any]:
        """
        Operator command: aborts the mission and commands all airborne drones to Return to Base (RTL).
        """
        self.mission_state = "RETURNING"
        recalled = []
        for agent in self.drones.values():
            if agent.status not in (DroneStatus.STANDBY, DroneStatus.RETURNING):
                agent._trigger_rtl()
                recalled.append(agent.id)
        return {
            "status": "SUCCESS",
            "mission_state": self.mission_state,
            "recalled_drones": recalled,
            "message": f"Procedura powrotu do bazy (RTL) aktywowana dla {len(recalled)} dronów.",
        }

    def swap_battery(self, drone_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Operator action: replaces depleted battery with a fresh 100% battery pack while drone is at base (STANDBY).
        """
        serviced = []
        target_drones = [self.drones[drone_id]] if (drone_id and drone_id in self.drones) else list(self.drones.values())

        for agent in target_drones:
            if agent.status == DroneStatus.STANDBY:
                agent.battery_pct = 100.0
                agent.needs_battery_swap = False
                agent.battery_swapped = True
                agent._rtl_triggered = False
                serviced.append(agent.id)

        if not serviced:
            return {
                "status": "ERROR",
                "success": False,
                "message": "Żaden dron nie oczekuje w bazie na wymianę baterii (status musi być STANDBY).",
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "serviced_drones": serviced,
            "message": f"Bateria wymieniona na 100% w: {', '.join(serviced)}. Dron(y) gotowe do ponownego wysłania.",
        }

    def relaunch_drone(self, drone_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Operator command: dispatches a serviced drone with fresh battery from base back into active search mission.
        """
        relaunched = []
        target_drones = [self.drones[drone_id]] if (drone_id and drone_id in self.drones) else list(self.drones.values())

        for agent in target_drones:
            if agent.status == DroneStatus.STANDBY:
                if agent.battery_pct < 25.0:
                    continue
                agent.relaunch(self.settings.swarm.search_altitude_m)
                relaunched.append(agent.id)

        if not relaunched:
            return {
                "status": "ERROR",
                "success": False,
                "message": "Brak dronów gotowych do startu (sprawdź poziom baterii oraz status STANDBY).",
            }

        self.mission_state = "RUNNING"
        return {
            "status": "SUCCESS",
            "success": True,
            "relaunched_drones": relaunched,
            "message": f"Dron(y) {', '.join(relaunched)} wystartowały i wznowiły realizację misji.",
        }

    def pause(self) -> None:
        self.mission_state = "PAUSED"
        # Save current drone states so they can be restored on resume
        self._saved_drone_states: Dict[str, DroneStatus] = {}
        for agent in self.drones.values():
            self._saved_drone_states[agent.id] = agent.status
            # Only override actively flying drones; leave STANDBY/RETURNING as-is
            if agent.status not in (DroneStatus.STANDBY, DroneStatus.RETURNING):
                agent.status = DroneStatus.HOVERING

    def resume(self) -> None:
        self.mission_state = "RUNNING"
        saved = getattr(self, "_saved_drone_states", {})
        for agent in self.drones.values():
            if agent.id in saved:
                # Restore the state the drone had before pause
                agent.status = saved[agent.id]
            elif agent.status == DroneStatus.HOVERING:
                # Fallback: if no saved state, resume searching
                agent.status = DroneStatus.SEARCHING
        self._saved_drone_states = {}

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
        self._init_gsm_sectors()
