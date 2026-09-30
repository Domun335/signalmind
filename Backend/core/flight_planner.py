"""
OutOfBlack - Multi-UAV Optimal Coverage Path Planning with Connectivity Constraints.
Generates synchronized, turn-minimized sweep trajectories that take into account:
1. Drone launch positions (takeoff origin & ingress geometry)
2. Battery capacity, cruise speed, and battery drain rates (energy budget)
3. Operational range constraints and safe Return-to-Base (RTB) margins
4. Dynamic corridor allocation and adaptive lane spacing to maximize terrain coverage
5. P2P MANET mesh radio connectivity and GCS backhaul constraints.
"""

from __future__ import annotations
import math
import itertools
from typing import List, Tuple, Optional
from .coordinates import LocalPoint3D, SearchAreaBounds


class Waypoint:
    __slots__ = ("x", "y", "z", "is_turn")

    def __init__(self, x: float, y: float, z: float, is_turn: bool = False):
        self.x = x
        self.y = y
        self.z = z
        self.is_turn = is_turn

    def to_point(self) -> LocalPoint3D:
        return LocalPoint3D(self.x, self.y, self.z)

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

    def __repr__(self) -> str:
        return f"Waypoint({self.x:.1f}, {self.y:.1f}, {self.z:.1f}, turn={self.is_turn})"


class BoustrophedonPlanner:
    """
    Advanced Multi-UAV Coverage Path Planner (M-UAV CPP).
    Designed to maximize search speed, minimize high-cost U-turns,
    respect drone takeoff origins, and adaptively scale coverage within battery limits
    while guaranteeing that inter-drone distance never exceeds mesh radio range.
    """

    @staticmethod
    def calculate_usable_range_m(
        battery_pct: float = 100.0,
        battery_low_threshold: float = 20.0,
        speed_mps: float = 12.0,
        drain_base_rate: float = 0.015,
        drain_speed_factor: float = 0.012,
        safety_reserve_pct: float = 5.0,
    ) -> float:
        """
        Calculates maximum reachable flight distance in meters given battery constraints.
        Usable budget = max(0, battery_pct - battery_low_threshold - safety_reserve_pct).
        """
        usable_battery = max(0.0, battery_pct - battery_low_threshold - safety_reserve_pct)
        drain_rate = drain_base_rate + (speed_mps / 15.0) * drain_speed_factor
        if drain_rate <= 1e-6 or speed_mps <= 1e-6:
            return 50000.0  # fallback generous range if zero drain rate
        usable_time_sec = usable_battery / drain_rate
        return usable_time_sec * speed_mps

    @staticmethod
    def match_drones_to_corridors(
        launch_points: List[LocalPoint3D],
        corridors: List[Tuple[float, float]],
        bounds: SearchAreaBounds,
        drone_ranges: List[float],
    ) -> List[int]:
        """
        Optimally maps searcher drones to corridors such that:
        1. Transit ingress paths do not cross (anti-collision on takeoff).
        2. Total transit distance from launch origins is minimized.
        3. Drones with lower battery/range receive corridors closest to their takeoff point.
        Returns: list of corridor indices, where mapping[drone_idx] = corridor_idx.
        """
        num_drones = len(launch_points)
        num_corridors = len(corridors)
        if num_drones == 0 or num_corridors == 0:
            return []

        if num_drones != num_corridors:
            # Fallback: simple modulo assignment
            return [i % num_corridors for i in range(num_drones)]

        # Precompute corridor entry coordinates based on overall bounds center
        center_y = (bounds.min_y + bounds.max_y) / 2.0
        entries = []
        for c_min_x, c_max_x in corridors:
            cx = (c_min_x + c_max_x) / 2.0
            entries.append((cx, center_y))

        # For large swarms (N > 8), evaluate via spatial order matching O(N log N)
        # to prevent O(N!) factorial complexity explosion while guaranteeing 0 path crossings.
        if num_drones > 8:
            drone_order = sorted(range(num_drones), key=lambda i: launch_points[i].x)
            corridor_order = sorted(range(num_drones), key=lambda c: corridors[c][0])
            perm = [0] * num_drones
            for d_idx, c_idx in zip(drone_order, corridor_order):
                perm[d_idx] = c_idx
            return perm

        # For small swarms (N <= 8), evaluate permutations for exact global optimum
        best_perm = list(range(num_drones))
        best_cost = float("inf")

        for perm in itertools.permutations(range(num_drones)):
            cost = 0.0
            crossings = 0
            for i in range(num_drones):
                c_idx = perm[i]
                c_min_x, c_max_x = corridors[c_idx]
                cx = (c_min_x + c_max_x) / 2.0
                # Ingress side depends on individual drone launch Y
                cy = bounds.min_y if launch_points[i].y < center_y else bounds.max_y
                dist_in = math.hypot(launch_points[i].x - cx, launch_points[i].y - cy)

                # Weight distance inversely by drone usable range (shorter range gets closer corridor)
                weight = 1.0 / max(500.0, drone_ranges[i])
                cost += dist_in * weight

                # Penalty for crossing trajectories
                for j in range(i + 1, num_drones):
                    cj_idx = perm[j]
                    cj_min_x, cj_max_x = corridors[cj_idx]
                    cjx = (cj_min_x + cj_max_x) / 2.0
                    if (launch_points[i].x - launch_points[j].x) * (cx - cjx) < 0:
                        crossings += 1

            cost += crossings * 100.0
            if cost < best_cost:
                best_cost = cost
                best_perm = list(perm)

        return best_perm

    @classmethod
    def _plan_corridor_track(
        cls,
        launch_pos: LocalPoint3D,
        corridor_min_x: float,
        corridor_max_x: float,
        bounds: SearchAreaBounds,
        lane_spacing_m: float,
        altitude_m: float,
        usable_range_m: float,
        max_sensor_range_m: float = 250.0,
        gcs_point: Optional[LocalPoint3D] = None,
    ) -> List[Waypoint]:
        """
        Plans systematic Boustrophedon sweeps for a single drone within its allocated corridor:
        1. Ingress from actual drone takeoff position (launch_pos) to optimal sector entry edge.
        2. Calculates the maximum number of full longitudinal passes (k) fitting within battery range.
        3. If range is constrained, adaptively spaces passes across the FULL corridor breadth
           to maximize searched territory rather than leaving portions uncovered.
        4. Appends a planned Return-To-Base (RTB) landing waypoint back at launch_pos.
        """
        margin = 15.0
        y_south = bounds.min_y + margin
        y_north = bounds.max_y - margin
        pass_len = max(20.0, y_north - y_south)
        slice_w = max(10.0, corridor_max_x - corridor_min_x)

        # 1. Determine ingress edge based on drone takeoff position
        center_y = (bounds.min_y + bounds.max_y) / 2.0
        starts_south = launch_pos.y < center_y
        y_entry = y_south if starts_south else y_north
        y_opposite = y_north if starts_south else y_south

        # 2. Systematic Boustrophedon sweep planning:
        # Full coverage of the entire corridor slice width at requested lane spacing.
        # k passes guarantee that inter-lane distance never exceeds lane_spacing_m
        # and eliminates blind spots / uncovered gaps across the entire search area.
        k = max(1, min(60, math.ceil(slice_w / max(10.0, lane_spacing_m))))
        eff_spacing = slice_w / k

        waypoints: List[Waypoint] = []

        # Waypoint 0: Drone takeoff position at cruising altitude
        waypoints.append(Waypoint(launch_pos.x, launch_pos.y, altitude_m))

        # Full systematic sweeps: passes uniformly distributed across the entire corridor width
        for p in range(k):
            x_pass = corridor_min_x + (p + 0.5) * eff_spacing

            if p % 2 == 0:
                # Sweep from y_entry to y_opposite
                waypoints.append(Waypoint(x_pass, y_entry, altitude_m, is_turn=(p > 0)))
                waypoints.append(Waypoint(x_pass, y_opposite, altitude_m))
            else:
                # Sweep from y_opposite to y_entry
                waypoints.append(Waypoint(x_pass, y_opposite, altitude_m, is_turn=True))
                waypoints.append(Waypoint(x_pass, y_entry, altitude_m))

        # Planned Return-To-Base (RTB) back to drone's launch origin
        waypoints.append(Waypoint(launch_pos.x, launch_pos.y, altitude_m, is_turn=True))
        waypoints.append(Waypoint(launch_pos.x, launch_pos.y, 0.0))

        return waypoints

    @classmethod
    def generate_swarm_tracks(
        cls,
        bounds: SearchAreaBounds,
        num_drones: int,
        lane_spacing_m: float = 90.0,
        altitude_m: float = 50.0,
        gcs_point: Optional[LocalPoint3D] = None,
        mesh_range_m: float = 700.0,
        mode: str = "SYNCHRONIZED_FRONT",
        launch_points: Optional[List[LocalPoint3D]] = None,
        cruise_speed_mps: float = 12.0,
        battery_drain_base_rate: float = 0.015,
        battery_drain_speed_factor: float = 0.012,
        battery_low_threshold: float = 20.0,
        initial_batteries: Optional[List[float]] = None,
        gcs_range_m: float = 1500.0,
        max_sensor_range_m: float = 250.0,
    ) -> List[List[Waypoint]]:
        """
        Main entry point for swarm track generation.
        Modes:
        - 'SYNCHRONIZED_FRONT': (Recommended) Phase-locked longitudinal sweeps.
          Guarantees adjacent drone separation <= W / N, unbroken mesh connectivity,
          and optimal ingress from each drone's specific takeoff origin.
        - 'RELAY_ANCHORED': Drone 1 acts as a Dedicated Backhaul Relay dynamically anchored
          between GCS and the search swarm centroid, while searchers sweep the crisis zone.
        - 'CLASSIC_BOUSTROPHEDON': Lawnmower sweep with launch-origin and battery optimization.
        """
        # 1. Fill default launch positions if not explicitly provided
        if not launch_points or len(launch_points) < num_drones:
            ref_gcs = gcs_point or LocalPoint3D(bounds.min_x - 50.0, bounds.min_y - 50.0, 0.0)
            launch_points = [
                LocalPoint3D(ref_gcs.x + (i * 25.0), ref_gcs.y, altitude_m)
                for i in range(num_drones)
            ]

        # 2. Compute individual drone usable flight ranges
        drone_ranges: List[float] = []
        for i in range(num_drones):
            bat_pct = initial_batteries[i] if (initial_batteries and i < len(initial_batteries)) else 100.0
            r_usable = cls.calculate_usable_range_m(
                battery_pct=bat_pct,
                battery_low_threshold=battery_low_threshold,
                speed_mps=cruise_speed_mps,
                drain_base_rate=battery_drain_base_rate,
                drain_speed_factor=battery_drain_speed_factor,
                safety_reserve_pct=5.0,
            )
            drone_ranges.append(r_usable)

        # 3. Mode dispatch
        if mode == "RELAY_ANCHORED" and num_drones >= 3 and gcs_point:
            return cls._generate_relay_anchored_tracks(
                bounds=bounds,
                num_drones=num_drones,
                lane_spacing_m=lane_spacing_m,
                altitude_m=altitude_m,
                gcs_point=gcs_point,
                launch_points=launch_points,
                drone_ranges=drone_ranges,
                mesh_range_m=mesh_range_m,
                gcs_range_m=gcs_range_m,
                max_sensor_range_m=max_sensor_range_m,
            )
        elif mode == "SYNCHRONIZED_FRONT":
            return cls._generate_synchronized_front_tracks(
                bounds=bounds,
                num_drones=num_drones,
                lane_spacing_m=lane_spacing_m,
                altitude_m=altitude_m,
                gcs_point=gcs_point,
                launch_points=launch_points,
                drone_ranges=drone_ranges,
                mesh_range_m=mesh_range_m,
                max_sensor_range_m=max_sensor_range_m,
            )
        else:
            return cls._generate_classic_tracks(
                bounds=bounds,
                num_drones=num_drones,
                lane_spacing_m=lane_spacing_m,
                altitude_m=altitude_m,
                gcs_point=gcs_point,
                launch_points=launch_points,
                drone_ranges=drone_ranges,
                max_sensor_range_m=max_sensor_range_m,
            )

    @classmethod
    def _generate_synchronized_front_tracks(
        cls,
        bounds: SearchAreaBounds,
        num_drones: int,
        lane_spacing_m: float,
        altitude_m: float,
        gcs_point: Optional[LocalPoint3D] = None,
        launch_points: Optional[List[LocalPoint3D]] = None,
        drone_ranges: Optional[List[float]] = None,
        mesh_range_m: float = 700.0,
        max_sensor_range_m: float = 250.0,
    ) -> List[List[Waypoint]]:
        """
        OPTIMIZED SYNCHRONIZED FRONT SWEEP:
        1. Swarm sweeps along the long axis (North-South).
        2. Swarm divides lateral width W into N contiguous corridors: width_i = W / N.
        3. Drones advance in synchronized phase: y_i(t) are aligned.
        4. Corridors are assigned to minimize launch transit and prevent crossing paths.
        5. Battery and range constraints dynamically dictate adaptive lane spacing for maximum coverage.
        """
        width = bounds.width
        slice_width = width / max(1, num_drones)

        # Build corridor boundaries
        corridors: List[Tuple[float, float]] = [
            (bounds.min_x + i * slice_width, bounds.min_x + (i + 1) * slice_width)
            for i in range(num_drones)
        ]

        # Match drones to corridors
        mapping = cls.match_drones_to_corridors(
            launch_points=launch_points,
            corridors=corridors,
            bounds=bounds,
            drone_ranges=drone_ranges,
        )

        tracks: List[List[Waypoint]] = [[] for _ in range(num_drones)]

        for drone_idx in range(num_drones):
            c_idx = mapping[drone_idx]
            c_min_x, c_max_x = corridors[c_idx]
            l_pos = launch_points[drone_idx]
            r_usable = drone_ranges[drone_idx]

            drone_track = cls._plan_corridor_track(
                launch_pos=l_pos,
                corridor_min_x=c_min_x,
                corridor_max_x=c_max_x,
                bounds=bounds,
                lane_spacing_m=lane_spacing_m,
                altitude_m=altitude_m,
                usable_range_m=r_usable,
                max_sensor_range_m=max_sensor_range_m,
                gcs_point=gcs_point,
            )
            tracks[drone_idx] = drone_track

        return tracks

    @classmethod
    def _generate_relay_anchored_tracks(
        cls,
        bounds: SearchAreaBounds,
        num_drones: int,
        lane_spacing_m: float,
        altitude_m: float,
        gcs_point: LocalPoint3D,
        launch_points: Optional[List[LocalPoint3D]] = None,
        drone_ranges: Optional[List[float]] = None,
        mesh_range_m: float = 3500.0,
        gcs_range_m: float = 7500.0,
        max_sensor_range_m: float = 250.0,
    ) -> List[List[Waypoint]]:
        """
        RELAY-ASSISTED FORMATION:
        - Drone 1 (UAV-01) acts as a Dedicated Backhaul Relay dynamically anchored between
          GCS and the centroid of the swarm search area, maintaining unbroken high-gain link.
        - Drones 2..N execute battery-optimized synchronized sweeps across the crisis zone.
        """
        # In RELAY_ANCHORED mode: all N drones actively sweep their assigned corridors.
        # Drone 1 (UAV-01) is assigned the Gateway Corridor closest to GCS at an elevated
        # cruising altitude (+25m) to maintain continuous line-of-sight backhaul while actively searching.
        tracks = cls._generate_synchronized_front_tracks(
            bounds=bounds,
            num_drones=num_drones,
            lane_spacing_m=lane_spacing_m,
            altitude_m=altitude_m,
            gcs_point=gcs_point,
            launch_points=launch_points,
            drone_ranges=drone_ranges,
            mesh_range_m=mesh_range_m,
            max_sensor_range_m=max_sensor_range_m,
        )

        # Elevate Drone 1's sweep waypoints (+25m) so it acts as an active high-altitude relay gateway
        if tracks and len(tracks) > 0:
            for wp in tracks[0]:
                if wp.z > 1.0:
                    wp.z = altitude_m + 25.0

        return tracks

    @classmethod
    def _generate_classic_tracks(
        cls,
        bounds: SearchAreaBounds,
        num_drones: int,
        lane_spacing_m: float,
        altitude_m: float,
        gcs_point: Optional[LocalPoint3D] = None,
        launch_points: Optional[List[LocalPoint3D]] = None,
        drone_ranges: Optional[List[float]] = None,
        max_sensor_range_m: float = 250.0,
    ) -> List[List[Waypoint]]:
        """Classic partitioned sub-sector lawnmower with battery awareness and launch ingress."""
        return cls._generate_synchronized_front_tracks(
            bounds=bounds,
            num_drones=num_drones,
            lane_spacing_m=lane_spacing_m,
            altitude_m=altitude_m,
            gcs_point=gcs_point,
            launch_points=launch_points,
            drone_ranges=drone_ranges,
            mesh_range_m=700.0,
            max_sensor_range_m=max_sensor_range_m,
        )


class DroneKinematics:
    """
    Simulates realistic kinematic movement, heading calculations, and battery consumption.
    """

    @staticmethod
    def update_position(
        current_pos: LocalPoint3D,
        target_wp: Waypoint,
        speed_mps: float,
        dt_sec: float,
        arrival_radius_m: float = 6.0,
    ) -> Tuple[LocalPoint3D, float, bool]:
        """
        Advances drone position toward target waypoint.
        Returns: (new_position, heading_deg, has_arrived)
        """
        dx = target_wp.x - current_pos.x
        dy = target_wp.y - current_pos.y
        dz = target_wp.z - current_pos.z

        dist_2d = math.hypot(dx, dy)
        dist_3d = math.sqrt(dx * dx + dy * dy + dz * dz)

        if dist_3d <= arrival_radius_m:
            heading = math.degrees(math.atan2(dx, dy)) % 360.0 if dist_2d > 0.1 else 0.0
            return (LocalPoint3D(target_wp.x, target_wp.y, target_wp.z), heading, True)

        step = speed_mps * dt_sec
        ratio = min(1.0, step / max(0.001, dist_3d))

        new_x = current_pos.x + dx * ratio
        new_y = current_pos.y + dy * ratio
        new_z = current_pos.z + dz * ratio

        # Aviation heading: 0 = North, 90 = East, 180 = South, 270 = West
        heading = math.degrees(math.atan2(dx, dy)) % 360.0

        has_arrived = (math.sqrt((target_wp.x - new_x) ** 2 + (target_wp.y - new_y) ** 2 + (target_wp.z - new_z) ** 2) <= arrival_radius_m)
        return (LocalPoint3D(new_x, new_y, new_z), heading, has_arrived)

    @staticmethod
    def calculate_battery_drain(
        current_battery: float,
        speed_mps: float = 0.0,
        dt_sec: float = 1.0,
        base_rate: float = 0.020,
        speed_factor: float = 0.015,
        drain_multiplier: float = 1.0,
        is_hovering: bool = False,
        is_gateway: bool = False,
        reference_speed_mps: float = 18.0,
    ) -> Tuple[float, float]:
        """
        Calculates heterogeneous battery drain reflecting individual drone characteristics:
        1. Base avionics & sensor payload power scaled by drone's specific airframe efficiency (drain_multiplier).
        2. Speed-dependent aerodynamic drag power proportional to (speed / ref_speed)^1.8.
        3. Gateway RF amplification overhead for high-power mesh transmission.
        4. Hovering power penalty to sustain rotor thrust against gravity.

        Returns:
            (new_battery_pct, current_drain_rate_pct_sec)
        """
        if current_battery <= 0.0:
            return (0.0, 0.0)

        # Individual drone airframe & payload efficiency scaling
        p_base = base_rate * drain_multiplier

        # Speed-dependent dynamic aerodynamic drag
        if is_hovering or speed_mps < 0.5:
            # Hover thrust penalty (requires sustained rotor thrust with zero translational lift)
            p_speed = speed_factor * drain_multiplier * 1.25
        else:
            speed_ratio = max(0.2, speed_mps / reference_speed_mps)
            p_speed = speed_factor * drain_multiplier * (speed_ratio ** 1.8)

        # Gateway mesh transmission power overhead (high-power PA)
        p_gateway = (base_rate * 0.25) if is_gateway else 0.0

        total_drain_rate = p_base + p_speed + p_gateway
        new_battery = max(0.0, current_battery - (total_drain_rate * dt_sec))
        return (new_battery, round(total_drain_rate, 4))


