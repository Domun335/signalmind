import math
import pytest
from simulation_engine import SimulationEngine
from models.telemetry import DroneStatus


def test_simulation_engine_lifecycle():
    engine = SimulationEngine()
    assert engine.mission_state == "IDLE"

    for agent in engine.drones.values():
        assert agent.status == DroneStatus.STANDBY

    engine.start()
    assert engine.mission_state == "RUNNING"
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.SEARCHING

    snapshot = engine.step(2.0)
    assert snapshot.mission_state == "RUNNING"
    assert snapshot.stats.elapsed_time_sec == 2.0
    assert len(snapshot.drones) == len(engine.drones)

    engine.pause()
    assert engine.mission_state == "PAUSED"
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.HOVERING

    engine.resume()
    assert engine.mission_state == "RUNNING"
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.SEARCHING

    engine.reset()
    assert engine.mission_state == "IDLE"
    assert engine.elapsed_time_sec == 0.0


def test_pause_preserves_standby_and_returning():
    engine = SimulationEngine()
    engine.pause()
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.STANDBY


def test_inject_and_inspect_poi():
    engine = SimulationEngine()
    engine.start()

    anon_id = engine.inject_poi(
        lat=50.0620,
        lon=19.9370,
        signal_type="WIFI_PROBE_REQ",
        tx_power_dbm=18.0,
    )
    assert anon_id.startswith("POI-")

    snapshot = engine.step(1.0)
    assert len(engine.emitters) >= 1

    result = engine.inspect_poi(anonymized_id=anon_id, altitude_m=30.0)
    assert result["success"] is True
    assigned_drone = result["drone_id"]
    assert assigned_drone in engine.drones
    assert engine.drones[assigned_drone].target_poi_id == anon_id

    resume_res = engine.resume_search(drone_id=assigned_drone)
    assert resume_res["success"] is True
    assert engine.drones[assigned_drone].target_poi_id is None


def test_heterogeneous_battery_drain_across_swarm():
    engine = SimulationEngine()
    engine.start()

    speeds = [d.speed_mps for d in engine.drones.values()]
    unique_speeds = set(speeds)
    assert len(unique_speeds) > 1, f"Expected varied drone speeds, got {unique_speeds}"

    for _ in range(20):
        engine.step(10.0)

    batteries = [d.battery_pct for d in engine.drones.values()]
    unique_batteries = set(batteries)
    assert len(unique_batteries) > 1, (
        f"Expected varied battery drain across drones, but all drones had identical levels: {batteries}"
    )

    uav1 = engine.drones["UAV-01"]
    uav3 = engine.drones["UAV-03"]
    assert uav1.battery_pct < uav3.battery_pct
    assert uav1.current_drain_rate > uav3.current_drain_rate

    snap = engine.step(1.0)
    for dt in snap.drones:
        assert dt.battery_drain_rate > 0.0


def test_mission_abort_and_rtl():
    engine = SimulationEngine()
    engine.start()
    assert engine.mission_state == "RUNNING"

    for _ in range(5):
        engine.step(2.0)

    abort_res = engine.abort()
    assert abort_res["status"] == "SUCCESS"
    assert engine.mission_state == "RETURNING"
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.RETURNING

    for _ in range(60):
        engine.step(5.0)
        if engine.mission_state == "IDLE":
            break

    assert engine.mission_state == "IDLE"
    for agent in engine.drones.values():
        assert agent.status == DroneStatus.STANDBY
        assert agent.pos.z == 0.0
        assert agent.needs_battery_swap is True


def test_low_battery_auto_rtl_landing_swap_and_relaunch():
    engine = SimulationEngine()
    engine.start()

    target_id = "UAV-01"
    agent = engine.drones[target_id]
    agent.battery_pct = 15.0

    engine.step(1.0)
    assert agent.status == DroneStatus.RETURNING

    for _ in range(40):
        engine.step(5.0)
        if agent.status == DroneStatus.STANDBY:
            break

    assert agent.status == DroneStatus.STANDBY
    assert agent.pos.z == 0.0
    assert agent.needs_battery_swap is True
    assert agent.battery_swapped is False

    relaunch_fail = engine.relaunch_drone(target_id)
    assert relaunch_fail["success"] is False
    assert agent.status == DroneStatus.STANDBY

    swap_res = engine.swap_battery(target_id)
    assert swap_res["success"] is True
    assert agent.battery_pct == 100.0
    assert agent.needs_battery_swap is False
    assert agent.battery_swapped is True

    relaunch_res = engine.relaunch_drone(target_id)
    assert relaunch_res["success"] is True
    assert agent.status == DroneStatus.TRANSIT
    assert agent._resuming_to_breakoff is True
    assert agent.pos.z == engine.settings.swarm.search_altitude_m
    assert agent.battery_swapped is False
    assert engine.mission_state == "RUNNING"

    for _ in range(15):
        engine.step(1.0)
        if agent.status == DroneStatus.SEARCHING:
            break
    assert agent.status == DroneStatus.SEARCHING
    assert agent._resuming_to_breakoff is False


def test_drone_resumes_at_exact_breakoff_position():
    engine = SimulationEngine()
    engine.start()

    target_id = "UAV-01"
    agent = engine.drones[target_id]

    for _ in range(10):
        engine.step(1.0)

    breakoff_x = agent.pos.x
    breakoff_y = agent.pos.y
    breakoff_z = agent.pos.z

    agent._trigger_rtl()
    assert agent.status == DroneStatus.RETURNING
    assert agent._breakoff_pos is not None
    assert abs(agent._breakoff_pos.x - breakoff_x) < 0.1
    assert abs(agent._breakoff_pos.y - breakoff_y) < 0.1

    for _ in range(50):
        engine.step(5.0)
        if agent.status == DroneStatus.STANDBY:
            break
    assert agent.status == DroneStatus.STANDBY

    swap_res = engine.swap_battery(target_id)
    assert swap_res["success"] is True

    relaunch_res = engine.relaunch_drone(target_id)
    assert relaunch_res["success"] is True
    assert agent.status == DroneStatus.TRANSIT
    assert agent._resuming_to_breakoff is True

    assert abs(agent.waypoints[0].x - breakoff_x) < 0.1
    assert abs(agent.waypoints[0].y - breakoff_y) < 0.1

    arrived_at_breakoff = False
    for _ in range(60):
        engine.step(2.0)
        if agent.status == DroneStatus.SEARCHING:
            arrived_at_breakoff = True
            break

    assert arrived_at_breakoff is True
    assert agent.status == DroneStatus.SEARCHING
    assert agent._resuming_to_breakoff is False
    dist_to_breakoff = math.sqrt((agent.pos.x - breakoff_x) ** 2 + (agent.pos.y - breakoff_y) ** 2)
    assert dist_to_breakoff <= agent.arrival_radius_m + 30.0


