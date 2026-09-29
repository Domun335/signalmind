"""
OutOfBlack - RF Propagation Models, GSM Blackout Gradient & Ground Emitters.
Simulates radio frequency attenuation, log-normal shadowing, and victim beacon emissions.
"""

from __future__ import annotations
import math
import random
import hashlib
from typing import List, Tuple, Optional
from dataclasses import dataclass
from .coordinates import LocalPoint3D, GeoReference, SearchAreaBounds
from models.telemetry import GSMPoint


class LogDistancePathLoss:
    """
    Standard ITU/IEEE Log-Distance Path Loss Model with Log-Normal Shadowing.
    RSSI(d) = Pt - PL0 - 10 * n * log10(d / d0) + X_sigma
    """

    def __init__(
        self,
        pl_0_dbm: float = 40.0,    # Path loss at d0 = 1.0 m (2.4 GHz)
        path_loss_exponent: float = 2.8,  # Rural/wooded disaster area
        shadowing_sigma_db: float = 2.0,  # Multipath & environmental variance
        rx_sensitivity_dbm: float = -95.0, # Minimum detectable RF threshold
    ):
        self.pl_0 = pl_0_dbm
        self.n = path_loss_exponent
        self.sigma = shadowing_sigma_db
        self.rx_sensitivity = rx_sensitivity_dbm

    def compute_rssi(
        self,
        distance_m: float,
        tx_power_dbm: float = 16.0,
        add_shadowing_noise: bool = True,
    ) -> float:
        """Computes received signal strength in dBm."""
        d = max(1.0, distance_m)
        path_loss = self.pl_0 + 10.0 * self.n * math.log10(d)
        noise = random.gauss(0.0, self.sigma) if add_shadowing_noise else 0.0
        rssi = tx_power_dbm - path_loss + noise
        return round(rssi, 1)

    def estimate_distance_from_rssi(
        self,
        rssi_dbm: float,
        tx_power_dbm: float = 16.0,
    ) -> float:
        """Inverts the log-distance equation to estimate Euclidean distance in meters."""
        # RSSI = Pt - PL0 - 10*n*log10(d)  =>  10*n*log10(d) = Pt - PL0 - RSSI
        delta = (tx_power_dbm - self.pl_0 - rssi_dbm) / (10.0 * self.n)
        return max(1.0, 10.0 ** delta)

    def is_detectable(self, rssi_dbm: float) -> bool:
        return rssi_dbm >= self.rx_sensitivity


class GSMBlackoutEnvironment:
    """
    Simulates cellular network degradation over the disaster sector.
    An operational macro-tower sits outside the crisis zone, with a steep exponential
    attenuation drop-off into the epicenter (fallen towers, structural collapse).
    """

    def __init__(
        self,
        bounds: SearchAreaBounds,
        tower_offset_m: float = 1200.0,
        normal_rssi_dbm: float = -65.0,
        blackout_rssi_dbm: float = -118.0,
        blackout_radius_m: float = 0.0,
        center_offset_x_m: float = 0.0,
        center_offset_y_m: float = 0.0,
        tower_offset_x_m: Optional[float] = None,
        tower_offset_y_m: Optional[float] = None,
    ):
        self.bounds = bounds
        self.tower_offset_m = tower_offset_m
        self.normal_rssi = normal_rssi_dbm
        self.blackout_rssi = blackout_rssi_dbm
        self.center_offset_x_m = center_offset_x_m
        self.center_offset_y_m = center_offset_y_m
        self.tower_offset_x_m = tower_offset_x_m
        self.tower_offset_y_m = tower_offset_y_m

        # Base station location
        if tower_offset_x_m is not None and tower_offset_y_m is not None:
            self.bts_x = bounds.center[0] + tower_offset_x_m
            self.bts_y = bounds.center[1] + tower_offset_y_m
        else:
            self.bts_x = bounds.min_x - tower_offset_m * 0.4
            self.bts_y = bounds.min_y - tower_offset_m * 0.4

        # Center of crisis zone where damage is concentrated
        self.crisis_cx = bounds.center[0] + center_offset_x_m
        self.crisis_cy = bounds.center[1] + center_offset_y_m
        default_radius = max(bounds.width, bounds.height) * 0.65
        self.crisis_radius = blackout_radius_m if (blackout_radius_m and blackout_radius_m > 0) else default_radius

    def get_gsm_rssi(self, x: float, y: float) -> float:
        """Calculates cellular RSSI at local coordinates (x, y)."""
        dist_to_crisis = math.hypot(x - self.crisis_cx, y - self.crisis_cy)
        # Normalized degradation factor: 0.0 at epicenter, 1.0 outside
        fade_factor = min(1.0, (dist_to_crisis / max(1.0, self.crisis_radius)) ** 1.8)

        rssi = self.blackout_rssi + (self.normal_rssi - self.blackout_rssi) * fade_factor
        # BUG-6 fix: deterministic spatial noise based on coordinates (consistent across resets)
        noise_seed = hash((round(x, 1), round(y, 1))) % 10000
        noise = ((noise_seed / 10000.0) * 3.0) - 1.5  # range: -1.5 to +1.5
        rssi += noise
        return round(max(-125.0, min(-55.0, rssi)), 1)

    def generate_grid_points(
        self,
        geo_ref: GeoReference,
        grid_resolution_m: float = 120.0,
    ) -> List[GSMPoint]:
        """
        Samples the operational area to produce a 2D scalar field of GSM coverage.
        Used by the frontend dashboard to render isolines / blackout heatmaps.
        """
        points: List[GSMPoint] = []
        x = self.bounds.min_x
        while x <= self.bounds.max_x:
            y = self.bounds.min_y
            while y <= self.bounds.max_y:
                rssi = self.get_gsm_rssi(x, y)
                geo = geo_ref.to_geo(x, y)

                if rssi >= -85.0:
                    status = "NORMAL"
                elif rssi >= -100.0:
                    status = "DEGRADED"
                else:
                    status = "BLACKOUT"

                points.append(
                    GSMPoint(
                        lat=round(geo.lat, 6),
                        lon=round(geo.lon, 6),
                        rssi_dbm=rssi,
                        status=status,
                    )
                )
                y += grid_resolution_m
            x += grid_resolution_m
        return points


class GroundEmitter:
    """
    Represents a victim's smartphone trapped in the blackout zone.
    Periodically emits RF burst probe requests (Wi-Fi 802.11 / LTE PRACH).
    """

    SALT = "OutOfBlack_Crisis2026_SecureSalt"

    def __init__(
        self,
        raw_id: str,
        pos: LocalPoint3D,
        signal_type: str = "WIFI_PROBE_REQ",
        tx_power_dbm: float = 16.0,
        burst_interval_sec: float = 5.0,
    ):
        self.raw_id = raw_id
        self.anonymized_id = self._anonymize(raw_id)
        self.pos = pos
        self.signal_type = signal_type
        self.tx_power = tx_power_dbm
        self.burst_interval = burst_interval_sec
        self._time_to_next_burst = random.uniform(0.5, burst_interval_sec)

    @classmethod
    def _anonymize(cls, raw: str) -> str:
        """Converts raw MAC/IMEI into a privacy-preserving SHA-256 tactical token."""
        h = hashlib.sha256((cls.SALT + raw).encode()).hexdigest()
        return f"POI-{h[:8].upper()}"

    def tick(self, dt: float) -> bool:
        """Advances time. Returns True if an RF burst is triggered this tick."""
        self._time_to_next_burst -= dt
        if self._time_to_next_burst <= 0.0:
            # Schedule next burst with jitter (+/- 1.5s)
            self._time_to_next_burst = max(2.0, self.burst_interval + random.uniform(-1.5, 1.5))
            return True
        return False
