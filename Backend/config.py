"""
OutOfBlack - Simulation Configuration Schema & Loader.
Primary configuration file: simulation_config.json
"""

from __future__ import annotations
import os
import re
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


def strip_json_comments(text: str) -> str:
    """Removes standard // and /* */ comments from JSON text before parsing."""
    pattern = r"//.*?$|/\*.*?\*/"
    return re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)


@dataclass
class AreaConfig:
    origin_lat: float = 50.0614
    origin_lon: float = 19.9366
    origin_alt: float = 0.0
    area_width_m: float = 4000.0
    area_height_m: float = 4000.0
    gcs_offset_x_m: float = -650.0
    gcs_offset_y_m: float = -650.0


@dataclass
class SwarmConfig:
    num_drones: int = 6
    cruise_speed_mps: float = 12.0
    search_altitude_m: float = 50.0
    lane_spacing_m: float = 90.0
    arrival_radius_m: float = 6.0
    battery_drain_base_rate: float = 0.020
    battery_drain_speed_factor: float = 0.015
    battery_low_threshold: float = 20.0
    planner_mode: str = "SYNCHRONIZED_FRONT"
    callsigns: List[str] = field(default_factory=lambda: [
        "Vulture-1", "Vulture-2", "Vulture-3", "Vulture-4", "Vulture-5", "Vulture-6"
    ])
    launch_offsets_m: Optional[List[Dict[str, float]]] = None
    max_sensor_range_m: float = 250.0


@dataclass
class RFPropagationConfig:
    pl_0_dbm: float = 40.0
    path_loss_exponent: float = 2.8
    shadowing_sigma_db: float = 2.0
    rx_sensitivity_dbm: float = -95.0


@dataclass
class MeshNetworkConfig:
    mesh_range_m: float = 700.0
    gcs_range_m: float = 800.0
    tx_power_dbm: float = 23.0
    mesh_sensitivity_dbm: float = -95.0


@dataclass
class GSMBlackoutConfig:
    normal_rssi_dbm: float = -65.0
    blackout_rssi_dbm: float = -118.0
    tower_offset_m: float = 1200.0
    grid_resolution_m: float = 140.0
    blackout_radius_m: float = 0.0
    center_offset_x_m: float = 0.0
    center_offset_y_m: float = 0.0
    tower_offset_x_m: Optional[float] = None
    tower_offset_y_m: Optional[float] = None


@dataclass
class EstimationConfig:
    max_history_observations: int = 25
    recency_decay_factor: float = 0.05
    base_uncertainty_radius_m: float = 120.0
    min_uncertainty_radius_m: float = 16.0


@dataclass
class VictimScenario:
    mac: str
    local_x: float
    local_y: float
    signal_type: str = "WIFI_PROBE_REQ"
    tx_power_dbm: float = 16.0
    burst_interval_sec: float = 5.0


@dataclass
class SimulationSettings:
    area: AreaConfig = field(default_factory=AreaConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    rf: RFPropagationConfig = field(default_factory=RFPropagationConfig)
    mesh: MeshNetworkConfig = field(default_factory=MeshNetworkConfig)
    gsm: GSMBlackoutConfig = field(default_factory=GSMBlackoutConfig)
    estimation: EstimationConfig = field(default_factory=EstimationConfig)
    victims: List[VictimScenario] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_to_file(self, filepath: str = "simulation_config.json") -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_file(cls, filepath: str = "simulation_config.json") -> SimulationSettings:
        if not os.path.exists(filepath):
            return cls()

        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = strip_json_comments(raw_text)
        data = json.loads(cleaned_text)

        # Helper to filter out comment/description keys starting with _
        def clean_kwargs(d: dict) -> dict:
            return {k: v for k, v in d.items() if not k.startswith("_")}

        area_data = clean_kwargs(data.get("area", {}))
        swarm_data = clean_kwargs(data.get("swarm", {}))
        rf_data = clean_kwargs(data.get("rf", {}))
        mesh_data = clean_kwargs(data.get("mesh", {}))
        gsm_data = clean_kwargs(data.get("gsm", {}))
        est_data = clean_kwargs(data.get("estimation", {}))
        victims_data = [clean_kwargs(v) for v in data.get("victims", [])]

        return cls(
            area=AreaConfig(**area_data),
            swarm=SwarmConfig(**swarm_data),
            rf=RFPropagationConfig(**rf_data),
            mesh=MeshNetworkConfig(**mesh_data),
            gsm=GSMBlackoutConfig(**gsm_data),
            estimation=EstimationConfig(**est_data),
            victims=[VictimScenario(**v) for v in victims_data],
        )


def load_simulation_config(filepath: str = "simulation_config.json") -> SimulationSettings:
    """Primary loader function: reads simulation_config.json (with fallback)."""
    return SimulationSettings.load_from_file(filepath)


# Fallback instance if JSON is missing
SIM_CONFIG = load_simulation_config()
