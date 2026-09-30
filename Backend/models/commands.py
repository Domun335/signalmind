"""
OutOfBlack - REST Command & Configuration Models.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class GeoCoordinate(BaseModel):
    lat: float
    lon: float


class BoundaryRequest(BaseModel):
    polygon: Optional[List[GeoCoordinate]] = Field(
        None,
        description="List of GPS coordinates forming polygon [p1, p2, p3, p4]"
    )
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [min_lat, min_lon, max_lat, max_lon]"
    )


class SimulationControlRequest(BaseModel):
    action: str = Field(..., description="'START', 'PAUSE', 'RESUME', 'RESET'")


class InjectPOIRequest(BaseModel):
    lat: float = Field(..., description="Latitude of victim device")
    lon: float = Field(..., description="Longitude of victim device")
    signal_type: str = Field(default="WIFI_PROBE_REQ", description="'WIFI_PROBE_REQ' or 'LTE_DIRECT_UPLINK'")
    raw_mac: Optional[str] = Field(None, description="Optional custom MAC/IMEI for demonstration")
    tx_power_dbm: float = Field(default=16.0, description="Transmit power in dBm")


class SimulationConfig(BaseModel):
    num_drones: int = Field(default=4, ge=2, le=8, description="Number of drones in swarm")
    drone_speed_mps: float = Field(default=12.0, ge=5.0, le=25.0, description="Cruise speed in m/s")
    drone_altitude_m: float = Field(default=50.0, ge=20.0, le=120.0, description="Flight altitude in meters")
    mesh_range_m: float = Field(default=650.0, ge=200.0, le=2000.0, description="Maximum P2P RF mesh distance")
    gcs_range_m: float = Field(default=750.0, ge=200.0, le=3000.0, description="Max direct GCS range")
    lane_spacing_m: float = Field(default=90.0, ge=40.0, le=250.0, description="Boustrophedon sweep spacing")


class InspectPOIRequest(BaseModel):
    anonymized_id: str = Field(..., description="ID of victim signal POI to inspect")
    drone_id: Optional[str] = Field(None, description="Optional specific drone ID (e.g. UAV-02). If None, closest available search drone is chosen.")
    altitude_m: Optional[float] = Field(35.0, ge=15.0, le=100.0, description="Altitude in meters to hover/orbit over victim")
    hover_duration_sec: Optional[float] = Field(None, description="Optional duration to hover in seconds before auto-resuming search. None = until manual resume.")


class ResumeSearchRequest(BaseModel):
    drone_id: Optional[str] = Field(None, description="Optional drone ID to resume original search track. If None, all inspecting drones resume.")


class SpeedRequest(BaseModel):
    multiplier: Optional[float] = Field(None, ge=0.1, le=50.0, description="Simulation speed multiplier")
    speed: Optional[float] = Field(None, ge=0.1, le=50.0, description="Alternative speed value")


class BatterySwapRequest(BaseModel):
    drone_id: Optional[str] = Field(None, description="Optional specific drone ID to swap battery for (e.g. UAV-01). If None, all landed standby drones are serviced.")


class RelaunchDroneRequest(BaseModel):
    drone_id: Optional[str] = Field(None, description="Optional specific drone ID to relaunch (e.g. UAV-01). If None, all serviced standby drones relaunch.")

