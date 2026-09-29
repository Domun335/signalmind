"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import { Eye, EyeOff, Layers, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const CARTO_API_KEY = process.env.NEXT_PUBLIC_CARTO_API_KEY || "cb1_43ac_1_8e135bd66ca3a7880d62f03e";

export function TacticalMap({ snapshot, focusedCoordinate, config }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef = useRef({
    boundary: null,
    flightPaths: null,
    meshLines: null,
    gcsRange: null,
    meshRange: null,
    drones: null,
    pois: null,
    gcs: null,
    gsmGrid: null,
  });

  const [showFlightPaths, setShowFlightPaths] = useState(true);
  const [showMeshRanges, setShowMeshRanges] = useState(true);
  const [showGcsRange, setShowGcsRange] = useState(true);
  const [showGsmBlackout, setShowGsmBlackout] = useState(true);
  const [activeBaseLayer, setActiveBaseLayer] = useState("carto"); // "carto", "esri", "satellite"
  const lastFittedAreaKeyRef = useRef(null);
  const lastGsmSignatureRef = useRef(null);

  // Keep stable refs to snapshot and config to prevent effects from re-triggering on telemetry ticks
  const snapshotRef = useRef(snapshot);
  useEffect(() => {
    snapshotRef.current = snapshot;
  }, [snapshot]);

  const configRef = useRef(config);
  useEffect(() => {
    configRef.current = config;
  }, [config]);

  // Center/Fit view to active area with completely stable reference
  const fitSearchArea = useCallback((animate = true) => {
    const map = mapInstanceRef.current;
    if (!map) return;
    map.invalidateSize();

    const snap = snapshotRef.current;
    const cfg = configRef.current;

    let bounds = null;
    if (snap?.boundary && snap.boundary.length > 0) {
      bounds = L.latLngBounds(snap.boundary);
    } else if (cfg?.area?.origin_lat && cfg?.area?.origin_lon) {
      const lat = parseFloat(cfg.area.origin_lat);
      const lon = parseFloat(cfg.area.origin_lon);
      const w = parseFloat(cfg.area.area_width_m) || 4000;
      const h = parseFloat(cfg.area.area_height_m) || 4000;
      const dLat = (h / 2) / 111139;
      const dLon = (w / 2) / (111139 * Math.cos((lat * Math.PI) / 180));
      bounds = L.latLngBounds([
        [lat - dLat, lon - dLon],
        [lat + dLat, lon + dLon],
      ]);
    }

    if (bounds && bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15, animate });
    }
  }, []);

  // Initialize Leaflet Map once
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Use initial coordinates from config, snapshot boundary, or default
    const initialLat =
      parseFloat(config?.area?.origin_lat) ||
      (snapshot?.boundary?.[0]?.[0] ? parseFloat(snapshot.boundary[0][0]) : 50.0614);
    const initialLon =
      parseFloat(config?.area?.origin_lon) ||
      (snapshot?.boundary?.[0]?.[1] ? parseFloat(snapshot.boundary[0][1]) : 19.9366);

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLon],
      zoom: 13,
      zoomControl: false,
      attributionControl: false,
    });
    mapInstanceRef.current = map;

    L.control.zoom({ position: "bottomright" }).addTo(map);

    // Basemaps
    const cartoDark = L.tileLayer(
      `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`,
      { maxZoom: 19, subdomains: "abcd" }
    );

    const esriDark = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 16 }
    );

    const esriSatellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19 }
    );

    cartoDark.addTo(map);

    // Layer groups for tactical elements
    layersRef.current.boundary = L.layerGroup().addTo(map);
    layersRef.current.flightPaths = L.layerGroup().addTo(map);
    layersRef.current.meshLines = L.layerGroup().addTo(map);
    layersRef.current.gcsRange = L.layerGroup().addTo(map);
    layersRef.current.meshRange = L.layerGroup().addTo(map);
    layersRef.current.gsmGrid = L.layerGroup().addTo(map);
    layersRef.current.gsmTower = L.layerGroup().addTo(map);
    layersRef.current.gsmCrisis = L.layerGroup().addTo(map);
    layersRef.current.gcs = L.layerGroup().addTo(map);
    layersRef.current.drones = L.layerGroup().addTo(map);
    layersRef.current.pois = L.layerGroup().addTo(map);

    // Basemap Switcher Control
    L.control
      .layers(
        {
          "CARTO Dark Matter (z kluczem)": cartoDark,
          "Esri Dark Canvas": esriDark,
          "Esri Satelita": esriSatellite,
        },
        null,
        { position: "topleft" }
      )
      .addTo(map);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Invalidate map size on container resize
  useEffect(() => {
    if (!mapContainerRef.current) return;
    const observer = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    });
    observer.observe(mapContainerRef.current);
    return () => observer.disconnect();
  }, []);

  // Delayed initial fit on mount ONCE to ensure CSS/container layout has stabilized
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mapInstanceRef.current) {
        fitSearchArea(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [fitSearchArea]);

  // Center on focused coordinate if requested (e.g. user clicked a specific drone or POI)
  useEffect(() => {
    if (focusedCoordinate && mapInstanceRef.current) {
      mapInstanceRef.current.setView([focusedCoordinate.lat, focusedCoordinate.lon], 16, {
        animate: true,
      });
    }
  }, [focusedCoordinate]);

  // Only auto-fit when the configuration location explicitly changes (stable primitive key)
  const areaLat = config?.area?.origin_lat;
  const areaLon = config?.area?.origin_lon;
  const areaW = config?.area?.area_width_m;
  const areaH = config?.area?.area_height_m;
  const areaKey = areaLat && areaLon ? `${areaLat}_${areaLon}_${areaW}_${areaH}` : null;

  useEffect(() => {
    if (!areaKey) return;
    if (lastFittedAreaKeyRef.current && lastFittedAreaKeyRef.current !== areaKey) {
      // User explicitly changed the area preset or coordinates in setup
      fitSearchArea(true);
    }
    lastFittedAreaKeyRef.current = areaKey;
  }, [areaKey, fitSearchArea]);

  // Render Telemetry Snapshot Elements onto Map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !snapshot) return;

    const { boundary, drones, mesh, gcs_position, pois, gsm_grid } = snapshot;

    // 1. Search Area Boundary Polygon
    const boundaryLayer = layersRef.current.boundary;
    boundaryLayer.clearLayers();
    if (boundary && boundary.length > 0) {
      L.polygon(boundary, {
        color: "#00f0ff",
        weight: 1.5,
        fillColor: "#00f0ff",
        fillOpacity: 0.02,
        dashArray: "4, 6",
      }).addTo(boundaryLayer);
    }

    // 3. GSM Blackout Grid, Tower & Crisis Center
    const gsmGridLayer = layersRef.current.gsmGrid;
    const gsmTowerLayer = layersRef.current.gsmTower;
    const gsmCrisisLayer = layersRef.current.gsmCrisis;

    if (!showGsmBlackout) {
      if (gsmGridLayer) gsmGridLayer.clearLayers();
      if (gsmTowerLayer) gsmTowerLayer.clearLayers();
      if (gsmCrisisLayer) gsmCrisisLayer.clearLayers();
      lastGsmSignatureRef.current = null;
    } else {
      const gsmSignature =
        gsm_grid && gsm_grid.length > 0
          ? `${gsm_grid.length}_${gsm_grid[0].lat}_${gsm_grid[0].lon}_${snapshot.gsm_crisis_center?.radius_m || 0}`
          : null;

      if (gsmSignature && gsmSignature !== lastGsmSignatureRef.current && gsmGridLayer) {
        gsmGridLayer.clearLayers();
        lastGsmSignatureRef.current = gsmSignature;
        gsm_grid.forEach((pt) => {
          let color = "#10b981";
          let opacity = 0.12;
          if (pt.status === "DEGRADED") {
            color = "#f59e0b";
            opacity = 0.25;
          }
          if (pt.status === "BLACKOUT") {
            color = "#ef4444";
            opacity = 0.4;
          }

          L.circle([pt.lat, pt.lon], {
            radius: 65,
            stroke: false,
            fillColor: color,
            fillOpacity: opacity,
          }).addTo(gsmGridLayer);
        });
      }

      if (gsmTowerLayer) {
        gsmTowerLayer.clearLayers();
      }

      // Render Crisis Blackout Boundary Circles
      if (gsmCrisisLayer) {
        gsmCrisisLayer.clearLayers();
        if (snapshot.gsm_crisis_center) {
          const { lat, lon, radius_m } = snapshot.gsm_crisis_center;
          L.circle([lat, lon], {
            radius: radius_m,
            color: "#f59e0b",
            weight: 1.5,
            dashArray: "5, 6",
            fillColor: "#f59e0b",
            fillOpacity: 0.04,
          })
            .bindTooltip(
              `<b>Strefa Awarii GSM</b>: promień ${(radius_m / 1000).toFixed(1)} km`,
              { sticky: true }
            )
            .addTo(gsmCrisisLayer);

          L.circle([lat, lon], {
            radius: radius_m * 0.65,
            color: "#ef4444",
            weight: 1.8,
            dashArray: "6, 6",
            fillColor: "#ef4444",
            fillOpacity: 0.08,
          }).addTo(gsmCrisisLayer);
        }
      }
    }

    // 4. Ground Control Station (GCS) & Coverage Range Circle
    const gcsLayer = layersRef.current.gcs;
    const gcsRangeLayer = layersRef.current.gcsRange;
    gcsLayer.clearLayers();
    gcsRangeLayer.clearLayers();

    if (gcs_position) {
      // GCS Pin Marker
      const gcsIcon = L.divIcon({
        className: "gcs-marker",
        html: `
          <div style="width:26px; height:26px; background:#10b981; border:2px solid #ffffff; border-radius:6px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 14px rgba(16,185,129,0.8);">
            <span style="font-size:12px; font-weight:900; color:#000000; font-family:monospace;">G</span>
          </div>
          <div style="font-family:monospace; font-size:10px; font-weight:700; color:#10b981; text-align:center; text-shadow:0 0 4px #000; margin-top:1px;">GCS</div>
        `,
        iconSize: [32, 38],
        iconAnchor: [16, 13],
      });

      L.marker([gcs_position.lat, gcs_position.lon], { icon: gcsIcon })
        .bindTooltip("<b>GCS (Ground Control Station)</b><br>Stanowisko dowodzenia & lądowisko", { sticky: true })
        .addTo(gcsLayer);

      // GCS C2 Range Circle (5000m)
      if (showGcsRange) {
        const gcsRangeM = mesh?.gcs_range_m || 5000.0;
        L.circle([gcs_position.lat, gcs_position.lon], {
          radius: gcsRangeM,
          color: "#ffb700",
          weight: 1.5,
          dashArray: "8, 8",
          fillColor: "#ffb700",
          fillOpacity: 0.03,
        })
          .bindTooltip(`<b>Zasięg C2 GCS</b>: ${gcsRangeM}m (${(gcsRangeM / 1000).toFixed(1)} km)`, { sticky: true })
          .addTo(gcsRangeLayer);
      }
    }

    // 5. Mesh Network Edges & Gateway P2P Coverage Circle
    const meshLinesLayer = layersRef.current.meshLines;
    const meshRangeLayer = layersRef.current.meshRange;
    meshLinesLayer.clearLayers();
    meshRangeLayer.clearLayers();

    const nodeLookup = {};
    if (mesh && mesh.nodes) {
      mesh.nodes.forEach((n) => {
        nodeLookup[n.id] = [n.lat, n.lon];
      });
    }

    const p2pRangeM = mesh?.mesh_range_m || 2500.0;

    // Draw P2P Mesh Range circle around the primary Gateway drone
    if (showMeshRanges && mesh?.gateway_id && nodeLookup[mesh.gateway_id]) {
      const gwPos = nodeLookup[mesh.gateway_id];
      L.circle(gwPos, {
        radius: p2pRangeM,
        color: "#00f0ff",
        weight: 1.2,
        dashArray: "5, 8",
        fillColor: "#00f0ff",
        fillOpacity: 0.03,
      })
        .bindTooltip(`<b>Zasięg P2P Gateway (${mesh.gateway_id})</b>: ${p2pRangeM}m (${(p2pRangeM / 1000).toFixed(1)} km)`, {
          sticky: true,
        })
        .addTo(meshRangeLayer);
    }

    // Render Mesh Edges
    if (mesh && mesh.edges) {
      mesh.edges.forEach((edge) => {
        const p1 = nodeLookup[edge.source];
        const p2 = nodeLookup[edge.target];
        if (p1 && p2) {
          const isGcsLink = edge.is_gateway_link || edge.source === "GCS-BASE" || edge.target === "GCS-BASE";
          const lineColor = isGcsLink ? "#ffb700" : "#00f0ff";
          const weight = isGcsLink ? 3.0 : 1.8;
          const opacity = isGcsLink ? 0.95 : 0.75;

          const poly = L.polyline([p1, p2], {
            color: lineColor,
            weight: weight,
            opacity: opacity,
            dashArray: isGcsLink ? "4, 6" : null,
          }).addTo(meshLinesLayer);

          const linkType = isGcsLink ? "⚡ C2 GATEWAY UPLINK" : "🔗 P2P AIR-TO-AIR MESH";
          poly.bindTooltip(
            `<div style="font-family:monospace; font-size:11px;">
              <b style="color:${lineColor}">${linkType}</b><br>
              ${edge.source} ↔ ${edge.target}<br>
              Dystans: <b>${edge.distance_m}m</b><br>
              RSSI: <b>${edge.rssi_dbm} dBm</b> | Jakość: <b>${edge.quality_pct}%</b>
            </div>`,
            { sticky: true }
          );
        }
      });
    }

    // 6. Planned Flight Paths (corridors per drone)
    const flightPathsLayer = layersRef.current.flightPaths;
    flightPathsLayer.clearLayers();

    if (showFlightPaths && drones) {
      const droneColors = ["#00f0ff", "#00ff88", "#ffb700", "#a855f7", "#ec4899", "#3b82f6", "#10b981", "#f97316"];
      drones.forEach((d, idx) => {
        if (d.planned_path && d.planned_path.length > 1) {
          const color = droneColors[idx % droneColors.length];
          L.polyline(d.planned_path, {
            color: color,
            weight: 2,
            dashArray: "5, 8",
            opacity: 0.65,
          }).addTo(flightPathsLayer);

          d.planned_path.forEach((pt, wpIdx) => {
            if (wpIdx > 0 && wpIdx < d.planned_path.length - 1) {
              L.circleMarker(pt, {
                radius: 3,
                color: color,
                fillColor: color,
                fillOpacity: 0.8,
                weight: 1,
              }).addTo(flightPathsLayer);
            }
          });
        }
      });
    }

    // 7. Active Drones (with heading orientation)
    const dronesLayer = layersRef.current.drones;
    dronesLayer.clearLayers();

    if (drones) {
      drones.forEach((d) => {
        const isGw = d.is_gateway;
        const color = isGw ? "#ffb700" : "#00f0ff";
        const strokeColor = isGw ? "#ffffff" : "#0099ff";

        const droneIcon = L.divIcon({
          className: "drone-marker",
          html: `
            <div style="transform: rotate(${d.heading_deg}deg); width:32px; height:32px; display:flex; align-items:center; justify-content:center;">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="${color}" stroke="${strokeColor}" stroke-width="1.5" style="filter: drop-shadow(0 0 6px ${color});">
                <polygon points="12 2, 19 21, 12 17, 5 21" />
              </svg>
            </div>
            <div style="font-family:monospace; font-size:10px; font-weight:700; color:#ffffff; text-shadow:0 0 6px #000, 0 0 2px #000; text-align:center; margin-top:-2px;">
              ${d.callsign}
            </div>
          `,
          iconSize: [36, 44],
          iconAnchor: [18, 16],
        });

        const marker = L.marker([d.lat, d.lon], { icon: droneIcon }).addTo(dronesLayer);
        marker.bindTooltip(
          `<div style="font-family:monospace; font-size:11px;">
            <b style="color:${color}">${d.callsign} (${d.id})</b> [${d.role}]<br>
            Wysokość: <b>${d.alt_m} m</b> | Prędkość: <b>${d.speed_mps} m/s</b><br>
            Bateria: <b>${d.battery_pct}%</b> | Status: <b>${d.status}</b><br>
            Pakiety RF: <b>${d.packets_sniffed}</b>
          </div>`,
          { sticky: true }
        );
      });
    }

    // 8. Localized Victim Signals (POIs) with CEP Uncertainty Circles and Radar Beacon
    const poisLayer = layersRef.current.pois;
    poisLayer.clearLayers();

    if (pois && pois.length > 0) {
      pois.forEach((poi) => {
        // Geodetic Uncertainty Circle
        L.circle([poi.est_lat, poi.est_lon], {
          radius: poi.uncertainty_radius_m,
          color: "#ff3366",
          weight: 1.5,
          dashArray: "5, 6",
          fillColor: "#ff3366",
          fillOpacity: 0.12,
          interactive: false,
        }).addTo(poisLayer);

        // Concentric Radar Beacon Pin
        const poiIcon = L.divIcon({
          className: "poi-marker-div",
          html: `
            <div class="poi-beacon-wrapper">
              <div class="poi-beacon-ripple"></div>
              <div class="poi-beacon-ripple delay"></div>
              <div class="poi-beacon-core">
                <span style="font-size:8px; line-height:1; color:#fff;">●</span>
              </div>
              <div class="poi-beacon-label">±${poi.uncertainty_radius_m.toFixed(0)}m</div>
            </div>
          `,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });

        const marker = L.marker([poi.est_lat, poi.est_lon], { icon: poiIcon }).addTo(poisLayer);
        marker.bindTooltip(
          `<div style="font-family:monospace; font-size:11px; padding:3px;">
            <b style="color:#ff3366;">🎯 WYKRYTY SYGNAŁ RF (OFIARA)</b><br>
            ID: <b>${poi.anonymized_id}</b><br>
            Typ: <b>${poi.signal_type}</b><br>
            Niepewność CEP: <b>±${poi.uncertainty_radius_m} m</b><br>
            Pewność: <b>${Math.round(poi.confidence * 100)}%</b><br>
            Odebrane pakiety: <b>${poi.detections_count}</b><br>
            Ostatnie RSSI: <b>${poi.last_rssi_dbm} dBm</b><br>
            Wykryty przez: <b>${poi.sniffed_by_drones.join(", ")}</b>
          </div>`,
          { sticky: true }
        );
      });
    }
  }, [snapshot, showFlightPaths, showMeshRanges, showGcsRange, showGsmBlackout]);

  return (
    <div className="relative w-full h-full min-h-0 flex-1 overflow-hidden rounded-lg border border-border/50 bg-[#090d16] shadow-xl">
      {/* Leaflet Map Canvas */}
      <div ref={mapContainerRef} className="w-full h-full min-h-0 z-10" />

      {/* Floating Tactical Layer Quick-Toggles */}
      <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-1.5 bg-card/85 backdrop-blur-md border border-border/60 p-1 rounded-lg shadow-2xl">
        <Button
          size="xs"
          variant="outline"
          onClick={() => fitSearchArea(true)}
          className="h-6 px-2 text-[10px] font-mono gap-1 text-cyan-400 border-cyan-500/40 bg-cyan-950/30 hover:bg-cyan-900/40 cursor-pointer"
          title="Dopasuj widok mapy do aktywnego obszaru poszukiwań"
        >
          <Maximize2 className="w-3 h-3" />
          Dopasuj do strefy
        </Button>

        <div className="h-4 w-px bg-border/50 mx-0.5" />

        <Button
          size="xs"
          variant={showFlightPaths ? "default" : "outline"}
          onClick={() => setShowFlightPaths(!showFlightPaths)}
          className={`h-6 px-2 text-[10px] font-mono gap-1 cursor-pointer ${
            showFlightPaths ? "bg-cyan-600 hover:bg-cyan-500 text-white" : "text-muted-foreground"
          }`}
        >
          {showFlightPaths ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Trasy UAV
        </Button>

        <Button
          size="xs"
          variant={showMeshRanges ? "default" : "outline"}
          onClick={() => setShowMeshRanges(!showMeshRanges)}
          className={`h-6 px-2 text-[10px] font-mono gap-1 cursor-pointer ${
            showMeshRanges ? "bg-cyan-900/60 text-cyan-300 border border-cyan-500/50" : "text-muted-foreground"
          }`}
        >
          {showMeshRanges ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Zasięg P2P
        </Button>

        <Button
          size="xs"
          variant={showGcsRange ? "default" : "outline"}
          onClick={() => setShowGcsRange(!showGcsRange)}
          className={`h-6 px-2 text-[10px] font-mono gap-1 cursor-pointer ${
            showGcsRange ? "bg-amber-900/60 text-amber-300 border border-amber-500/50" : "text-muted-foreground"
          }`}
        >
          {showGcsRange ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Zasięg GCS
        </Button>

        <Button
          size="xs"
          variant={showGsmBlackout ? "default" : "outline"}
          onClick={() => setShowGsmBlackout(!showGsmBlackout)}
          className={`h-6 px-2 text-[10px] font-mono gap-1 cursor-pointer ${
            showGsmBlackout ? "bg-rose-950/70 text-rose-300 border border-rose-500/50" : "text-muted-foreground"
          }`}
        >
          {showGsmBlackout ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Blackout GSM
        </Button>
      </div>
    </div>
  );
}
