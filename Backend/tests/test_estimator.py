import pytest
from core.coordinates import LocalPoint3D, GeoReference
from core.estimator import POITracker


def test_poi_tracker_localization_and_convergence():
    tracker = POITracker(
        recency_decay_factor=0.95,
        base_uncertainty_radius_m=80.0,
        min_uncertainty_radius_m=8.0,
    )
    geo_ref = GeoReference(origin_lat=50.0614, origin_lon=19.9366)

    # 1st observation: drone at (100, 200) detects signal with RSSI corresponding to ~50m
    tracker.record_detection(
        anonymized_id="POI-TEST01",
        signal_type="WIFI_PROBE_REQ",
        drone_id="UAV-01",
        drone_pos=LocalPoint3D(100.0, 200.0, 30.0),
        rssi_dbm=-65.0,
        sim_time=10.0,
    )

    estimates = tracker.get_all_estimates(geo_ref, current_sim_time=10.0)
    assert len(estimates) == 1
    poi = estimates[0]
    assert poi.anonymized_id == "POI-TEST01"
    assert poi.detections_count == 1
    assert poi.confidence < 0.6
    init_uncertainty = poi.uncertainty_radius_m

    # 2nd & 3rd observations from different drone angles
    tracker.record_detection(
        anonymized_id="POI-TEST01",
        signal_type="WIFI_PROBE_REQ",
        drone_id="UAV-02",
        drone_pos=LocalPoint3D(200.0, 200.0, 30.0),
        rssi_dbm=-65.0,
        sim_time=12.0,
    )
    tracker.record_detection(
        anonymized_id="POI-TEST01",
        signal_type="WIFI_PROBE_REQ",
        drone_id="UAV-03",
        drone_pos=LocalPoint3D(150.0, 250.0, 30.0),
        rssi_dbm=-65.0,
        sim_time=14.0,
    )

    estimates = tracker.get_all_estimates(geo_ref, current_sim_time=15.0)
    poi2 = estimates[0]
    assert poi2.detections_count == 3
    # Uncertainty circle should shrink with more observations from multiple drones
    assert poi2.uncertainty_radius_m < init_uncertainty
    # Confidence should increase
    assert poi2.confidence > poi.confidence
