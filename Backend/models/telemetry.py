"""
OutOfBlack - Real-Time Telemetry & Simulation Data Models.
Pydantic v2 schemas used for WebSocket broadcasting and REST telemetry endpoints.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DroneStatus(str, Enum):
    STANDBY = "STANDBY"
    SEARCHING = "SEARCHING"
    TRANSIT = "TRANSIT"
    RELAY = "RELAY"
    HOVERING = "HOVERING"
    RETURNING = "RETURNING"
    LOW_BATTERY = "LOW_BATTERY"


class DroneRole(str, Enum):
    SEARCHER = "SEARCHER"
    GATEWAY = "GATEWAY"  # Direct high-bandwidth link to GCS
    RELAY = "RELAY"      # Extended mesh node keeping remote searchers connected


class DroneTelemetry(BaseModel):
    id: str = Field(..., description="Unique drone identifier, e.g. UAV-01")
    callsign: str = Field(..., description="Tactical callsign, e.g. Vulture-1")
    lat: float = Field(..., description="WGS84 Latitude")
    lon: float = Field(..., description="WGS84 Longitude")
    alt_m: float = Field(..., description="Altitude Above Ground Level in meters")
    heading_deg: float = Field(..., description="Heading 0-360 degrees")
    speed_mps: float = Field(..., description="Ground speed in m/s")
    battery_pct: float = Field(..., description="Battery charge percentage (0-100)")
    status: DroneStatus = Field(default=DroneStatus.SEARCHING)
    role: DroneRole = Field(default=DroneRole.SEARCHER)
    is_gateway: bool = Field(default=False, description="True if this UAV serves as GCS uplink")
    packets_sniffed: int = Field(default=0, description="Cumulative RF probe packets captured")
    current_lane: int = Field(default=0, description="Assigned Boustrophedon search lane index")
    planned_path: List[List[float]] = Field(default_factory=list, description="Planned flight route waypoints [[lat, lon], ...]")
    target_poi_id: Optional[str] = Field(default=None, description="ID of victim signal POI currently being inspected in hover mode")
    needs_battery_swap: bool = Field(default=False, description="True if drone landed with depleted battery and awaits fresh battery pack")
    battery_swapped: bool = Field(default=False, description="True if battery was freshly swapped and drone is ready to relaunch")
    battery_drain_rate: float = Field(default=0.0, description="Current real-time battery drain rate in %/sec")


class MeshNode(BaseModel):
    id: str
    type: str = Field(..., description="'DRONE' or 'GCS'")
    lat: float
    lon: float
    is_gateway: bool = False


class MeshEdge(BaseModel):
    source: str
    target: str
    distance_m: float
    rssi_dbm: float
    quality_pct: float = Field(..., description="Link quality index 0-100%")
    is_gateway_link: bool = Field(default=False, description="True if this is an active C2 backhaul link to GCS")


class MeshTopology(BaseModel):
    nodes: List[MeshNode]
    edges: List[MeshEdge]
    gateway_id: Optional[str] = Field(None, description="Current primary gateway drone ID")
    gcs_connected: bool = Field(..., description="True if mesh has live path to Ground Station")
    routes_to_gcs: Dict[str, List[str]] = Field(default_factory=dict, description="Multi-hop path per node")
    mesh_range_m: float = Field(default=2500.0, description="Air-to-Air P2P Mesh maximum range in meters")
    gcs_range_m: float = Field(default=5000.0, description="Ground-to-Air GCS C2 maximum range in meters")


class GSMPoint(BaseModel):
    lat: float
    lon: float
    rssi_dbm: float
    status: str = Field(..., description="'NORMAL' (-85+ dBm), 'DEGRADED' (-100 to -85 dBm), or 'BLACKOUT' (<-100 dBm)")


class GSMSector(BaseModel):
    id: str = Field(..., description="Tactical sector identifier e.g. A1, B2")
    name: str = Field(..., description="Sector name e.g. Sektor A-1")
    bounds: List[List[float]] = Field(..., description="WGS84 polygon coordinates [[lat, lon], ...]")
    center_lat: float
    center_lon: float
    surveyed: bool = Field(default=False, description="True if a drone has surveyed RF in this sector")
    status: str = Field(default="UNKNOWN", description="'UNKNOWN', 'NORMAL', 'DEGRADED', 'BLACKOUT'")
    avg_rssi_dbm: Optional[float] = Field(default=None, description="Average measured GSM RSSI in dBm")
    surveyed_by: Optional[str] = Field(default=None, description="Callsign of surveying UAV")
    surveyed_time_sec: Optional[float] = Field(default=None, description="Mission elapsed seconds when surveyed")


class POIEstimate(BaseModel):
    anonymized_id: str = Field(..., description="SHA-256 hashed and salted device ID")
    signal_type: str = Field(..., description="'WIFI_PROBE_REQ' or 'LTE_DIRECT_UPLINK'")
    est_lat: float = Field(..., description="Estimated victim latitude")
    est_lon: float = Field(..., description="Estimated victim longitude")
    uncertainty_radius_m: float = Field(..., description="Error radius in meters (circle on map)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Estimation confidence score (0-1)")
    detections_count: int = Field(..., description="Total RF bursts recorded by swarm")
    last_seen_epoch: float = Field(..., description="Timestamp of most recent RF pulse")
    last_rssi_dbm: float = Field(..., description="Latest RSSI recorded")
    sniffed_by_drones: List[str] = Field(default_factory=list, description="IDs of UAVs that heard this device")
    is_being_inspected: bool = Field(default=False, description="True if a UAV is currently hovering/inspecting this POI")
    inspecting_drone_id: Optional[str] = Field(default=None, description="Callsign or ID of UAV currently inspecting")


class SimulationStats(BaseModel):
    elapsed_time_sec: float
    active_drones: int
    total_search_area_sqm: float
    area_covered_pct: float
    packets_intercepted: int
    pois_discovered: int
    gcs_online: bool
    mesh_links_count: int
    gsm_sectors_total: int = 0
    gsm_sectors_surveyed: int = 0
    gsm_sectors_blackout: int = 0
    gsm_recon_pct: float = 0.0


class MissionSnapshot(BaseModel):
    timestamp: str
    mission_state: str = Field(..., description="'RUNNING', 'PAUSED', 'STOPPED'")
    drones: List[DroneTelemetry]
    mesh: MeshTopology
    gsm_grid: List[GSMPoint]
    pois: List[POIEstimate]
    stats: SimulationStats
    boundary: List[List[float]] = Field(..., description="Search polygon coordinates [[lat, lon], ...]")
    gcs_position: Dict[str, float] = Field(..., description="Ground Control Station {lat, lon}")
    gsm_tower_position: Optional[Dict[str, float]] = Field(None, description="Surviving Macro GSM Tower {lat, lon}")
    gsm_crisis_center: Optional[Dict[str, float]] = Field(None, description="GSM Blackout Epicenter {lat, lon, radius_m}")
    gsm_sectors: List[GSMSector] = Field(default_factory=list, description="Tactical reconnaissance sectors surveyed by drones")

