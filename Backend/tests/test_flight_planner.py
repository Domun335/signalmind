import pytest
from core.coordinates import LocalPoint3D, SearchAreaBounds
from core.flight_planner import BoustrophedonPlanner


def test_usable_range_calculation():
    # 100% battery, threshold 20%, reserve 5% => usable = 75%
    usable_range = BoustrophedonPlanner.calculate_usable_range_m(
        battery_pct=100.0,
        battery_low_threshold=20.0,
        speed_mps=12.0,
        drain_base_rate=0.015,
        drain_speed_factor=0.012,
        safety_reserve_pct=5.0,
    )
    assert usable_range > 1000.0

    # Low battery <= 25% should return 0 usable range
    zero_range = BoustrophedonPlanner.calculate_usable_range_m(
        battery_pct=25.0,
        battery_low_threshold=20.0,
        safety_reserve_pct=5.0,
    )
    assert zero_range == 0.0


def test_corridor_matching_small_swarm():
    bounds = SearchAreaBounds(min_x=0.0, max_x=1000.0, min_y=0.0, max_y=1000.0)
    corridors = [(i * 250.0, (i + 1) * 250.0) for i in range(4)]
    launch_points = [
        LocalPoint3D(100.0, -50.0, 0.0),
        LocalPoint3D(350.0, -50.0, 0.0),
        LocalPoint3D(650.0, -50.0, 0.0),
        LocalPoint3D(900.0, -50.0, 0.0),
    ]
    drone_ranges = [5000.0] * 4

    perm = BoustrophedonPlanner.match_drones_to_corridors(
        launch_points=launch_points,
        corridors=corridors,
        bounds=bounds,
        drone_ranges=drone_ranges,
    )
    assert len(perm) == 4
    # All corridors should be uniquely assigned
    assert sorted(perm) == [0, 1, 2, 3]


def test_corridor_matching_large_swarm_exceeding_8():
    bounds = SearchAreaBounds(min_x=0.0, max_x=2400.0, min_y=0.0, max_y=1000.0)
    num_drones = 12
    step_w = 2400.0 / num_drones
    corridors = [(i * step_w, (i + 1) * step_w) for i in range(num_drones)]
    launch_points = [
        LocalPoint3D(i * step_w + 10.0, -50.0, 0.0) for i in range(num_drones)
    ]
    drone_ranges = [5000.0] * num_drones

    # Must complete instantly without O(N!) factorial explosion
    perm = BoustrophedonPlanner.match_drones_to_corridors(
        launch_points=launch_points,
        corridors=corridors,
        bounds=bounds,
        drone_ranges=drone_ranges,
    )
    assert len(perm) == num_drones
    assert sorted(perm) == list(range(num_drones))


def test_generate_swarm_tracks():
    bounds = SearchAreaBounds(min_x=-500.0, max_x=500.0, min_y=-500.0, max_y=500.0)
    gcs = LocalPoint3D(0.0, -550.0, 0.0)

    tracks = BoustrophedonPlanner.generate_swarm_tracks(
        bounds=bounds,
        num_drones=4,
        lane_spacing_m=100.0,
        altitude_m=45.0,
        gcs_point=gcs,
        mode="SYNCHRONIZED_FRONT",
    )

    assert len(tracks) == 4
    for waypoints in tracks:
        assert len(waypoints) > 2
        # Airborne sweep waypoints should have altitude == 45.0
        airborne_wps = [wp for wp in waypoints if wp.z > 0.0]
        assert len(airborne_wps) >= 2
        for wp in airborne_wps:
            assert wp.z == 45.0


def test_heterogeneous_battery_drain():
    from core.flight_planner import DroneKinematics

    # Compare battery drain at 12 m/s vs 22 m/s over 100 seconds
    bat_slow, rate_slow = DroneKinematics.calculate_battery_drain(
        current_battery=100.0,
        speed_mps=12.0,
        dt_sec=100.0,
        base_rate=0.035,
        speed_factor=0.025,
        drain_multiplier=1.0,
        is_hovering=False,
    )
    bat_fast, rate_fast = DroneKinematics.calculate_battery_drain(
        current_battery=100.0,
        speed_mps=22.0,
        dt_sec=100.0,
        base_rate=0.035,
        speed_factor=0.025,
        drain_multiplier=1.0,
        is_hovering=False,
    )

    # Flying faster MUST consume more battery (lower remaining percentage, higher rate)
    assert rate_fast > rate_slow
    assert bat_fast < bat_slow

    # Drain multiplier (e.g. 1.35x vs 0.78x) creates distinct heterogeneous consumption
    bat_heavy, rate_heavy = DroneKinematics.calculate_battery_drain(
        current_battery=100.0,
        speed_mps=18.0,
        dt_sec=100.0,
        base_rate=0.035,
        speed_factor=0.025,
        drain_multiplier=1.35,
    )
    bat_light, rate_light = DroneKinematics.calculate_battery_drain(
        current_battery=100.0,
        speed_mps=18.0,
        dt_sec=100.0,
        base_rate=0.035,
        speed_factor=0.025,
        drain_multiplier=0.78,
    )
    assert rate_heavy > rate_light
    assert bat_heavy < bat_light


def test_full_corridor_coverage_no_blind_spots():
    bounds = SearchAreaBounds(min_x=-5000.0, max_x=5000.0, min_y=-5000.0, max_y=5000.0)
    gcs = LocalPoint3D(-1500.0, -1500.0, 0.0)
    lane_spacing_m = 180.0
    sensor_range_m = 250.0

    tracks = BoustrophedonPlanner.generate_swarm_tracks(
        bounds=bounds,
        num_drones=4,
        lane_spacing_m=lane_spacing_m,
        altitude_m=80.0,
        gcs_point=gcs,
        mode="SYNCHRONIZED_FRONT",
        max_sensor_range_m=sensor_range_m,
    )

    assert len(tracks) == 4
    for track in tracks:
        # Full corridor coverage must generate full multi-pass sweeps (e.g. 14 passes = 31 waypoints)
        assert len(track) >= 28

    # Extract all sweep X-coordinates across the entire swarm
    all_sweep_x = []
    for track in tracks:
        sweep_x = sorted(list({round(wp.x, 1) for wp in track if abs(wp.y) > 4000.0 and wp.z > 1.0}))
        all_sweep_x.extend(sweep_x)

    all_sweep_x = sorted(all_sweep_x)
    assert len(all_sweep_x) >= 40

    # Spacing between any adjacent flight passes across the ENTIRE 10km area must be <= lane_spacing_m
    for i in range(len(all_sweep_x) - 1):
        gap = all_sweep_x[i + 1] - all_sweep_x[i]
        assert gap <= lane_spacing_m + 1.0
        assert gap < sensor_range_m * 2.0  # 100% overlapping sensor coverage

    # Boundary coverage: edges of search area are fully within sensor detection footprint
    assert all_sweep_x[0] - bounds.min_x < sensor_range_m
    assert bounds.max_x - all_sweep_x[-1] < sensor_range_m



