import pytest
from core.coordinates import LocalPoint3D
from core.mesh_network import MeshRouter


def test_mesh_network_direct_and_multihop():
    router = MeshRouter(
        mesh_range_m=500.0,
        gcs_range_m=600.0,
        tx_power_dbm=20.0,
        sensitivity_dbm=-95.0,
    )

    gcs = LocalPoint3D(0.0, 0.0, 0.0)
    drone_positions = {
        # UAV-01: 200m from GCS (direct link, eligible for gateway)
        "UAV-01": LocalPoint3D(200.0, 0.0, 40.0),
        # UAV-02: 400m from UAV-01, 600m from GCS (multi-hop via UAV-01)
        "UAV-02": LocalPoint3D(600.0, 0.0, 40.0),
    }

    topology = router.compute_topology(drone_positions, gcs)

    # UAV-01 should be gateway
    assert topology.gateway_id == "UAV-01"
    assert topology.gcs_connected is True

    # Check routing
    routes = topology.routes_to_gcs
    assert routes["UAV-01"] == ["UAV-01", "GCS-BASE"]
    assert routes["UAV-02"] == ["UAV-02", "UAV-01", "GCS-BASE"]


def test_mesh_network_partitioned_drone():
    router = MeshRouter(
        mesh_range_m=500.0,
        gcs_range_m=600.0,
        tx_power_dbm=20.0,
        sensitivity_dbm=-95.0,
    )

    gcs = LocalPoint3D(0.0, 0.0, 0.0)
    drone_positions = {
        "UAV-01": LocalPoint3D(200.0, 0.0, 40.0),
        # UAV-03: far away (isolated from both UAV-01 and GCS)
        "UAV-03": LocalPoint3D(3000.0, 0.0, 40.0),
    }

    topology = router.compute_topology(drone_positions, gcs)
    # Since UAV-03 is disconnected, the entire swarm is not fully connected to GCS
    assert topology.gcs_connected is False
    assert "UAV-03" not in topology.routes_to_gcs or topology.routes_to_gcs["UAV-03"] == []
