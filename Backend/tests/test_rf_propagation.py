import pytest
from core.coordinates import LocalPoint3D, SearchAreaBounds
from core.rf_propagation import LogDistancePathLoss, GSMBlackoutEnvironment, GroundEmitter


def test_log_distance_path_loss():
    model = LogDistancePathLoss(pl_0_dbm=40.0, path_loss_exponent=3.0, rx_sensitivity_dbm=-110.0)

    # At 1 meter without noise: RSSI = Pt - PL0 = 20 - 40 = -20 dBm
    rssi_1m = model.compute_rssi(distance_m=1.0, tx_power_dbm=20.0, add_shadowing_noise=False)
    assert rssi_1m == pytest.approx(-20.0)

    # At 10 meters: RSSI = 20 - 40 - 10 * 3 * log10(10) = -20 - 30 = -50 dBm
    rssi_10m = model.compute_rssi(distance_m=10.0, tx_power_dbm=20.0, add_shadowing_noise=False)
    assert rssi_10m == pytest.approx(-50.0)

    # Inverse distance estimate
    est_d = model.estimate_distance_from_rssi(rssi_dbm=-50.0, tx_power_dbm=20.0)
    assert est_d == pytest.approx(10.0, rel=1e-3)


def test_ground_emitter_anonymization():
    p = LocalPoint3D(10.0, 20.0, 0.0)
    emitter1 = GroundEmitter(raw_id="AA:BB:CC:DD:EE:FF", pos=p)
    emitter2 = GroundEmitter(raw_id="AA:BB:CC:DD:EE:FF", pos=p)

    # Consistent hashing for same MAC within same session
    assert emitter1.anonymized_id == emitter2.anonymized_id
    assert emitter1.anonymized_id.startswith("POI-")
    # Never expose raw MAC
    assert "AA:BB" not in emitter1.anonymized_id


def test_gsm_blackout_environment():
    bounds = SearchAreaBounds(min_x=-500.0, max_x=500.0, min_y=-500.0, max_y=500.0)
    gsm = GSMBlackoutEnvironment(
        bounds,
        normal_rssi_dbm=-65.0,
        blackout_rssi_dbm=-110.0,
        blackout_radius_m=300.0,
    )

    # Center of crisis zone should have blackout level signal
    rssi_center = gsm.get_gsm_rssi(gsm.crisis_cx, gsm.crisis_cy)
    assert rssi_center <= -100.0

    # Near BTS should have strong normal signal
    rssi_bts = gsm.get_gsm_rssi(gsm.bts_x, gsm.bts_y)
    assert rssi_bts >= -75.0
