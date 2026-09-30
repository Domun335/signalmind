import math
import pytest
from core.coordinates import LocalPoint3D, GeoReference, SearchAreaBounds


def test_local_point_distance():
    p1 = LocalPoint3D(0.0, 0.0, 0.0)
    p2 = LocalPoint3D(3.0, 4.0, 0.0)
    assert math.isclose(p1.distance_to(p2), 5.0, rel_tol=1e-5)
    assert math.isclose(p1.distance_2d(p2), 5.0, rel_tol=1e-5)

    p3 = LocalPoint3D(0.0, 0.0, 10.0)
    assert math.isclose(p1.distance_to(p3), 10.0, rel_tol=1e-5)
    assert math.isclose(p1.distance_2d(p3), 0.0, rel_tol=1e-5)


def test_geo_reference_roundtrip():
    ref = GeoReference(origin_lat=50.0614, origin_lon=19.9366, origin_alt=220.0)
    test_lat, test_lon, test_alt = 50.0650, 19.9400, 250.0

    # Convert to local ENU
    local = ref.to_local(test_lat, test_lon, test_alt)
    assert abs(local.x) > 0
    assert abs(local.y) > 0
    assert math.isclose(local.z, 30.0, abs_tol=1e-2)

    # Convert back to WGS84
    geo = ref.to_geo(local.x, local.y, local.z)
    assert math.isclose(geo.lat, test_lat, abs_tol=1e-5)
    assert math.isclose(geo.lon, test_lon, abs_tol=1e-5)
    assert math.isclose(geo.alt, test_alt, abs_tol=1e-2)


def test_search_area_bounds():
    bounds = SearchAreaBounds(min_x=-100.0, max_x=100.0, min_y=-200.0, max_y=200.0)
    assert bounds.width == 200.0
    assert bounds.height == 400.0
    assert bounds.center == (0.0, 0.0)
