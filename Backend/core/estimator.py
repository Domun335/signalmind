"""
OutOfBlack - RF Data Processing, Multilateration & Uncertainty Circle Estimation.
Converts raw intercepted RSSI bursts into geolocated victim points with shrinking uncertainty radii.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .coordinates import LocalPoint3D, GeoReference
from .rf_propagation import LogDistancePathLoss
from models.telemetry import POIEstimate


@dataclass
class RFObservation:
    drone_id: str
    drone_pos: LocalPoint3D
    rssi_dbm: float
    sim_timestamp: float  # simulation elapsed time (not wall-clock)
    estimated_distance_m: float


class POITracker:
    """
    Maintains historical RF observations for each anonymized device.
    Applies Weighted Centroid Localization (WCL) and trilateration
    to compute (x, y) estimates, uncertainty circles, and confidence scores.
    """

    def __init__(
        self,
        path_loss_model: Optional[LogDistancePathLoss] = None,
        max_history_len: int = 25,
        recency_decay_factor: float = 0.05,
        base_uncertainty_radius_m: float = 120.0,
        min_uncertainty_radius_m: float = 16.0,
    ):
        self.rf_model = path_loss_model or LogDistancePathLoss()
        # Key: anonymized_id -> List of RFObservation
        self._history: Dict[str, List[RFObservation]] = {}
        # Key: anonymized_id -> signal_type
        self._signal_types: Dict[str, str] = {}
        self.max_history_len = max_history_len
        self.recency_decay_factor = recency_decay_factor
        self.base_uncertainty_radius_m = base_uncertainty_radius_m
        self.min_uncertainty_radius_m = min_uncertainty_radius_m

    def record_detection(
        self,
        anonymized_id: str,
        signal_type: str,
        drone_id: str,
        drone_pos: LocalPoint3D,
        rssi_dbm: float,
        tx_power_dbm: float = 16.0,
        sim_time: float = 0.0,
    ) -> None:
        """Adds a newly intercepted RF burst from a drone."""
        if anonymized_id not in self._history:
            self._history[anonymized_id] = []
            self._signal_types[anonymized_id] = signal_type

        est_dist = self.rf_model.estimate_distance_from_rssi(rssi_dbm, tx_power_dbm)

        obs = RFObservation(
            drone_id=drone_id,
            drone_pos=LocalPoint3D(drone_pos.x, drone_pos.y, drone_pos.z),
            rssi_dbm=rssi_dbm,
            sim_timestamp=sim_time,
            estimated_distance_m=est_dist,
        )

        self._history[anonymized_id].append(obs)
        if len(self._history[anonymized_id]) > self.max_history_len:
            self._history[anonymized_id].pop(0)

    def estimate_poi(
        self,
        anonymized_id: str,
        geo_ref: GeoReference,
        current_sim_time: float = 0.0,
    ) -> Optional[POIEstimate]:
        """
        Computes the current localized estimate and uncertainty boundary for a POI.
        """
        obs_list = self._history.get(anonymized_id)
        if not obs_list:
            return None

        n_obs = len(obs_list)
        last_obs = obs_list[-1]
        unique_drones = {obs.drone_id for obs in obs_list}

        # Weighted Centroid Localization (WCL):
        # Weights inversely proportional to squared estimated distance
        total_weight = 0.0
        sum_x = 0.0
        sum_y = 0.0

        for obs in obs_list:
            # Add recency weight: recent packets have higher fidelity
            # Uses simulation time for consistency at any speed multiplier
            age_sec = max(0.1, current_sim_time - obs.sim_timestamp)
            recency = 1.0 / (1.0 + self.recency_decay_factor * age_sec)

            weight = (1.0 / max(10.0, obs.estimated_distance_m ** 1.8)) * recency
            total_weight += weight
            sum_x += obs.drone_pos.x * weight
            sum_y += obs.drone_pos.y * weight

        if total_weight > 0:
            est_x = sum_x / total_weight
            est_y = sum_y / total_weight
        else:
            est_x = last_obs.drone_pos.x
            est_y = last_obs.drone_pos.y

        # Refine if we have >= 3 diverse drone positions
        if len(unique_drones) >= 2 and n_obs >= 4:
            est_x, est_y = self._refine_least_squares(obs_list, est_x, est_y)

        # Calculate geometric diversity (GDOP-like factor)
        # Check standard deviation of drone observation positions
        xs = [obs.drone_pos.x for obs in obs_list]
        ys = [obs.drone_pos.y for obs in obs_list]
        spread_x = max(xs) - min(xs)
        spread_y = max(ys) - min(ys)
        spatial_diversity = math.hypot(spread_x, spread_y)

        # Uncertainty radius calculation (meters):
        diversity_factor = max(0.6, 1.0 - min(0.4, spatial_diversity / 400.0))
        base_radius = self.base_uncertainty_radius_m / math.sqrt(n_obs)
        uncertainty_radius = max(self.min_uncertainty_radius_m, min(140.0, base_radius * diversity_factor))

        # Confidence calculation: 0.2 to 0.98
        drone_bonus = min(0.3, (len(unique_drones) - 1) * 0.15)
        obs_bonus = min(0.45, (n_obs / 15.0) * 0.45)
        confidence = round(min(0.98, 0.25 + drone_bonus + obs_bonus), 2)

        geo_est = geo_ref.to_geo(est_x, est_y)

        return POIEstimate(
            anonymized_id=anonymized_id,
            signal_type=self._signal_types.get(anonymized_id, "WIFI_PROBE_REQ"),
            est_lat=round(geo_est.lat, 6),
            est_lon=round(geo_est.lon, 6),
            uncertainty_radius_m=round(uncertainty_radius, 1),
            confidence=confidence,
            detections_count=n_obs,
            last_seen_epoch=last_obs.sim_timestamp,
            last_rssi_dbm=last_obs.rssi_dbm,
            sniffed_by_drones=list(unique_drones),
        )

    def _refine_least_squares(
        self,
        obs_list: List[RFObservation],
        init_x: float,
        init_y: float,
        iterations: int = 4,
    ) -> Tuple[float, float]:
        """Iterative non-linear gradient descent refinement for multilateration."""
        x, y = init_x, init_y
        lr = 0.08  # step size

        for _ in range(iterations):
            grad_x = 0.0
            grad_y = 0.0
            for obs in obs_list:
                pred_dist = math.hypot(x - obs.drone_pos.x, y - obs.drone_pos.y)
                error = pred_dist - obs.estimated_distance_m
                if pred_dist > 0.1:
                    grad_x += error * ((x - obs.drone_pos.x) / pred_dist)
                    grad_y += error * ((y - obs.drone_pos.y) / pred_dist)

            x -= lr * (grad_x / len(obs_list))
            y -= lr * (grad_y / len(obs_list))

        return x, y

    def get_all_estimates(self, geo_ref: GeoReference, current_sim_time: float = 0.0) -> List[POIEstimate]:
        estimates = []
        for anon_id in self._history.keys():
            est = self.estimate_poi(anon_id, geo_ref, current_sim_time=current_sim_time)
            if est:
                estimates.append(est)
        # Sort by most recently detected or highest confidence
        estimates.sort(key=lambda p: (p.confidence, p.last_seen_epoch), reverse=True)
        return estimates

    def clear(self) -> None:
        self._history.clear()
        self._signal_types.clear()
