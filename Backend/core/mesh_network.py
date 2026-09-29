"""
OutOfBlack - P2P Mesh Network, Ad-Hoc Routing & Gateway Election.
Simulates RF mesh connectivity between UAVs and the Ground Control Station (GCS).
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Set, Tuple
from collections import deque
from .coordinates import LocalPoint3D
from models.telemetry import MeshNode, MeshEdge, MeshTopology, DroneRole


class MeshRouter:
    """
    Simulates dynamic ad-hoc 802.11ah / COFDM mesh topology.
    Handles dynamic neighbor discovery, link quality estimation,
    gateway election to GCS, and multi-hop routing paths.
    """

    def __init__(
        self,
        mesh_range_m: float = 700.0,
        gcs_range_m: float = 800.0,
        tx_power_dbm: float = 23.0,
        sensitivity_dbm: float = -95.0,
    ):
        self.mesh_range = mesh_range_m
        self.gcs_range = gcs_range_m
        self.tx_power = tx_power_dbm
        self.sensitivity = sensitivity_dbm

    def _calc_link_metrics(self, distance_m: float, max_range: float) -> Tuple[float, float]:
        """Calculates RF RSSI (dBm) and Link Quality Index (0-100%)."""
        if distance_m > max_range:
            return -120.0, 0.0

        d = max(1.0, distance_m)
        # Free-space / aerial path loss exponent n=2.2
        pl_0 = 40.0  # path loss at d0=1m
        rssi = self.tx_power - (pl_0 + 10.0 * 2.2 * math.log10(d))
        # BUG-4 fix: max RSSI reference derived from tx_power instead of hardcoded -40 dBm
        max_rssi = self.tx_power - pl_0  # RSSI at d=1m (best case)
        rssi_range = max(1.0, max_rssi - self.sensitivity)
        quality = max(0.0, min(100.0, ((rssi - self.sensitivity) / rssi_range) * 100.0))
        return round(rssi, 1), round(quality, 1)

    def compute_topology(
        self,
        drone_positions: Dict[str, LocalPoint3D],
        gcs_position: LocalPoint3D,
    ) -> MeshTopology:
        """
        Builds graph of nodes & edges, evaluates GCS connectivity,
        and elects the primary Gateway drone.
        """
        all_nodes: List[MeshNode] = []
        edges: List[MeshEdge] = []
        adjacency: Dict[str, List[str]] = {}

        # 1. Add GCS node (at local coordinate space)
        gcs_id = "GCS-BASE"
        adjacency[gcs_id] = []

        # 2. Add Drone nodes & initialize adjacency
        for drone_id in drone_positions.keys():
            adjacency[drone_id] = []

        # 3. Inter-drone links
        drone_ids = list(drone_positions.keys())
        for i in range(len(drone_ids)):
            u_id = drone_ids[i]
            pos_u = drone_positions[u_id]

            for j in range(i + 1, len(drone_ids)):
                v_id = drone_ids[j]
                pos_v = drone_positions[v_id]

                dist = pos_u.distance_to(pos_v)
                if dist <= self.mesh_range:
                    rssi, quality = self._calc_link_metrics(dist, self.mesh_range)
                    edges.append(
                        MeshEdge(
                            source=u_id,
                            target=v_id,
                            distance_m=round(dist, 1),
                            rssi_dbm=rssi,
                            quality_pct=quality,
                        )
                    )
                    adjacency[u_id].append(v_id)
                    adjacency[v_id].append(u_id)

        # 4. Search candidates for GCS Gateway (nodes within GCS coverage)
        gateway_candidates: List[Tuple[str, float, float]] = []  # (drone_id, rssi, quality)

        for drone_id, pos in drone_positions.items():
            dist_to_gcs = pos.distance_to(gcs_position)
            if dist_to_gcs <= self.gcs_range:
                rssi, quality = self._calc_link_metrics(dist_to_gcs, self.gcs_range)
                gateway_candidates.append((drone_id, rssi, quality))

        # 5. Elect primary Gateway drone (strongest link to GCS)
        primary_gateway_id: Optional[str] = None
        if gateway_candidates:
            gateway_candidates.sort(key=lambda x: x[1], reverse=True)
            primary_gateway_id = gateway_candidates[0][0]

            # Primary gateway link to GCS (the active C2 backhaul)
            gw_pos = drone_positions[primary_gateway_id]
            dist_gw = gw_pos.distance_to(gcs_position)
            rssi_gw, qual_gw = self._calc_link_metrics(dist_gw, self.gcs_range)
            edges.append(
                MeshEdge(
                    source=primary_gateway_id,
                    target=gcs_id,
                    distance_m=round(dist_gw, 1),
                    rssi_dbm=rssi_gw,
                    quality_pct=qual_gw,
                    is_gateway_link=True,
                )
            )
            adjacency[primary_gateway_id].append(gcs_id)
            adjacency[gcs_id].append(primary_gateway_id)

        # 6. Multi-hop routing to GCS using BFS through the Gateway
        routes_to_gcs: Dict[str, List[str]] = {}
        queue = deque([(gcs_id, [gcs_id])])
        visited = {gcs_id}

        while queue:
            curr_node, path = queue.popleft()
            for neighbor in adjacency.get(curr_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    if neighbor != gcs_id:
                        routes_to_gcs[neighbor] = new_path[::-1]  # from drone to GCS
                    queue.append((neighbor, new_path))

        # Fallback: if any partitioned drone cannot reach the primary gateway but is within direct GCS range
        for cand_id, rssi_c, qual_c in gateway_candidates:
            if cand_id != primary_gateway_id and cand_id not in routes_to_gcs:
                dist_c = drone_positions[cand_id].distance_to(gcs_position)
                edges.append(
                    MeshEdge(
                        source=cand_id,
                        target=gcs_id,
                        distance_m=round(dist_c, 1),
                        rssi_dbm=rssi_c,
                        quality_pct=qual_c,
                        is_gateway_link=True,
                    )
                )
                routes_to_gcs[cand_id] = [cand_id, gcs_id]

        # Whole swarm connected if all drones have a route to GCS
        all_drones_connected = all(d in routes_to_gcs for d in drone_positions.keys()) if drone_positions else False

        # Build node metadata
        for drone_id, pos in drone_positions.items():
            all_nodes.append(
                MeshNode(
                    id=drone_id,
                    type="DRONE",
                    lat=0.0,  # Will be populated with GPS in engine
                    lon=0.0,
                    is_gateway=(drone_id == primary_gateway_id),
                )
            )

        all_nodes.append(
            MeshNode(
                id=gcs_id,
                type="GCS",
                lat=0.0,
                lon=0.0,
                is_gateway=False,
            )
        )

        return MeshTopology(
            nodes=all_nodes,
            edges=edges,
            gateway_id=primary_gateway_id,
            gcs_connected=all_drones_connected,
            routes_to_gcs=routes_to_gcs,
            mesh_range_m=self.mesh_range,
            gcs_range_m=self.gcs_range,
        )
