import pytest
from starlette.testclient import TestClient
from main import app


@pytest.fixture
def client():
    # Use TestClient with lifespan
    with TestClient(app) as test_client:
        yield test_client


def test_api_root(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "OutOfBlack" in data["service"]
    assert data["docs"] == "/docs"


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert "active_drones" in data


def test_simulation_state_endpoint(client):
    res = client.get("/simulation/state")
    assert res.status_code == 200
    data = res.json()
    assert "drones" in data
    assert "mesh" in data
    assert "stats" in data


def test_simulation_lifecycle_endpoints(client):
    # Start
    res = client.post("/simulation/start")
    assert res.status_code == 200
    assert res.json()["mission_state"] == "RUNNING"

    # Pause
    res = client.post("/simulation/pause")
    assert res.status_code == 200
    assert res.json()["mission_state"] == "PAUSED"

    # Resume
    res = client.post("/simulation/resume")
    assert res.status_code == 200
    assert res.json()["mission_state"] == "RUNNING"

    # Speed 10x and 25x
    res = client.post("/simulation/speed", json={"multiplier": 10.0})
    assert res.status_code == 200
    assert res.json()["speed_multiplier"] == 10.0

    res = client.post("/simulation/speed", json={"multiplier": 25.0})
    assert res.status_code == 200
    assert res.json()["speed_multiplier"] == 25.0

    # Get speed
    res = client.get("/simulation/speed")
    assert res.status_code == 200
    assert res.json()["speed_multiplier"] == 25.0

    # Reset
    res = client.post("/simulation/reset")
    assert res.status_code == 200
    assert res.json()["mission_state"] == "IDLE"


def test_inject_and_inspect_api(client):
    client.post("/simulation/start")

    # Inject
    inj_res = client.post(
        "/simulation/inject-poi",
        json={
            "lat": 50.0618,
            "lon": 19.9372,
            "signal_type": "WIFI_PROBE_REQ",
            "tx_power_dbm": 16.0,
        },
    )
    assert inj_res.status_code == 200
    anon_id = inj_res.json()["anonymized_id"]

    # Inspect POI
    insp_res = client.post(
        "/mission/inspect-poi",
        json={"anonymized_id": anon_id, "altitude_m": 35.0},
    )
    assert insp_res.status_code == 200
    assert insp_res.json()["success"] is True

    # Resume search
    resm_res = client.post(
        "/mission/resume-search",
        json={"drone_id": insp_res.json()["drone_id"]},
    )
    assert resm_res.status_code == 200
    assert resm_res.json()["success"] is True


def test_cors_headers(client):
    res = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_config_endpoint_security(client):
    res = client.get("/config")
    assert res.status_code == 200
    data = res.json()
    assert "carto_tile_url" in data
    # Raw CARTO API key should not be exposed directly as a field
    assert "carto_api_key" not in data


def test_abort_battery_swap_and_relaunch_api(client):
    # Reset and start
    client.post("/simulation/reset")
    client.post("/simulation/start")

    # Abort mission
    res_abort = client.post("/mission/abort")
    assert res_abort.status_code == 200
    assert res_abort.json()["status"] == "SUCCESS"
    assert res_abort.json()["mission_state"] == "RETURNING"

    # Also test /simulation/abort alias
    res_abort_alias = client.post("/simulation/abort")
    assert res_abort_alias.status_code == 200
    assert res_abort_alias.json()["status"] == "SUCCESS"

    # Reset to put drones in STANDBY
    client.post("/simulation/reset")

    # Swap battery
    res_swap = client.post("/mission/swap-battery", json={"drone_id": "UAV-01"})
    assert res_swap.status_code == 200
    assert res_swap.json()["success"] is True

    # Relaunch drone
    res_relaunch = client.post("/mission/relaunch-drone", json={"drone_id": "UAV-01"})
    assert res_relaunch.status_code == 200
    assert res_relaunch.json()["success"] is True

