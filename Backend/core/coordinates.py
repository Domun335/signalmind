"""
OutOfBlack - Geodetic and Local Metric (ENU) Coordinate System.
Provides fast, numerically stable conversions between WGS84 (lat, lon, alt)
and local Cartesian coordinate space (East, North, Up in meters).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple, List

EARTH_RADIUS_METERS = 6371000.0


@dataclass(slots=True)
class GeoPoint:
    lat: float
    lon: float
    alt: float = 0.0

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.lat, self.lon, self.alt)


@dataclass(slots=True)
class LocalPoint3D:
    x: float  # East (meters)
    y: float  # North (meters)
    z: float  # Up / Altitude (meters)

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def distance_to(self, other: LocalPoint3D) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def distance_2d(self, other: LocalPoint3D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class GeoReference:
    """
    Local tangent plane origin projection (East-North-Up / Flat-Earth approximation).
    Accurate to within millimeters over typical tactical UAV operations (10x10 km).
    """

    def __init__(self, origin_lat: float, origin_lon: float, origin_alt: float = 0.0):
        self.lat0 = origin_lat
        self.lon0 = origin_lon
        self.alt0 = origin_alt
        self._lat0_rad = math.radians(origin_lat)
        self._lon0_rad = math.radians(origin_lon)
        self._cos_lat0 = math.cos(self._lat0_rad)

    def to_local(self, lat: float, lon: float, alt: float = 0.0) -> LocalPoint3D:
        """Convert GPS WGS84 (lat, lon, alt) to metric Cartesian (x=East, y=North, z=Up)."""
        d_lat = math.radians(lat - self.lat0)
        d_lon = math.radians(lon - self.lon0)

        x = d_lon * EARTH_RADIUS_METERS * self._cos_lat0
        y = d_lat * EARTH_RADIUS_METERS
        z = alt - self.alt0
        return LocalPoint3D(x=x, y=y, z=z)

    def to_geo(self, x: float, y: float, z: float = 0.0) -> GeoPoint:
        """Convert metric Cartesian (x, y, z) back to GPS WGS84 (lat, lon, alt)."""
        d_lat_rad = y / EARTH_RADIUS_METERS
        d_lon_rad = x / (EARTH_RADIUS_METERS * self._cos_lat0)

        lat = self.lat0 + math.degrees(d_lat_rad)
        lon = self.lon0 + math.degrees(d_lon_rad)
        alt = self.alt0 + z
        return GeoPoint(lat=lat, lon=lon, alt=alt)

    def haversine_distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two GPS coordinates."""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return EARTH_RADIUS_METERS * c


@dataclass
class SearchAreaBounds:
    """Axis-aligned bounding box in local metric coordinates."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)
