"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import {
  Search,
  MapPin,
  Crosshair,
  Building,
  Plus,
  Trash2,
  Navigation,
  X,
  Maximize2,
  Radio,
  Wifi,
  Sparkles,
  Move,
  Minus,
  Lock,
  Unlock,
  Square,
  Compass,
  AlertCircle,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const CARTO_API_KEY =
  process.env.NEXT_PUBLIC_CARTO_API_KEY || "cb1_43ac_1_8e135bd66ca3a7880d62f03e";

// Quick SAR Terrain Presets for fast navigation across Poland
const QUICK_LOCATIONS = [
  { name: "Tatry / Zakopane", lat: 49.2992, lon: 19.9395, desc: "Teren wysokogórski" },
  { name: "Kraków", lat: 50.0614, lon: 19.9366, desc: "Obszar zurbanizowany" },
  { name: "Bieszczady", lat: 49.1245, lon: 22.6512, desc: "Pasma leśne i połoniny" },
  { name: "Babia Góra", lat: 49.5731, lon: 19.5292, desc: "Odosobniony masyw leśny" },
  { name: "Gorce / Nowy Targ", lat: 49.4833, lon: 20.0333, desc: "Dolina i lasy iglaste" },
  { name: "Śląsk / Katowice", lat: 50.2649, lon: 19.0238, desc: "Aglomeracja przemysłowa" },
  { name: "Warszawa", lat: 52.2297, lon: 21.0122, desc: "Strefa metropolitalna" },
  { name: "Gdańsk / Bałtyk", lat: 54.3722, lon: 18.6383, desc: "Linia brzegowa SAR" },
];

export function SetupMapPreview({
  config,
  onUpdateArea,
  onUpdateGsm,
  onAddVictim,
  onUpdateVictim,
  onRemoveVictim,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

  // Layer groups
  const layersRef = useRef({
    boundary: null,
    handles: null,
    labels: null,
    centerGrip: null,
    gsmBlackout: null,
    gsmTower: null,
    gsmHandles: null,
    gcs: null,
    gcsRange: null,
    victims: null,
    drawTemp: null,
  });

  // Interaction Mode: "view" | "box_draw" | "set_center" | "set_gcs" | "add_victim" | "edit_gsm"
  const [interactionMode, setInteractionMode] = useState("view");
  const [victimSignalType, setVictimSignalType] = useState("WIFI_PROBE_REQ");
  const [isSquareLocked, setIsSquareLocked] = useState(false);
  const [feedbackToast, setFeedbackToast] = useState(null);

  const interactionModeRef = useRef("view");
  const victimSignalTypeRef = useRef("WIFI_PROBE_REQ");
  const isSquareLockedRef = useRef(false);
  const lastPresetCenterRef = useRef(null);

  useEffect(() => {
    interactionModeRef.current = interactionMode;
  }, [interactionMode]);

  useEffect(() => {
    victimSignalTypeRef.current = victimSignalType;
  }, [victimSignalType]);

  useEffect(() => {
    isSquareLockedRef.current = isSquareLocked;
  }, [isSquareLocked]);

  // Keep references to callbacks for Leaflet event handlers
  const callbacksRef = useRef({
    onUpdateArea,
    onUpdateGsm,
    onAddVictim,
    onUpdateVictim,
    onRemoveVictim,
    config,
  });
  useEffect(() => {
    callbacksRef.current = {
      onUpdateArea,
      onUpdateGsm,
      onAddVictim,
      onUpdateVictim,
      onRemoveVictim,
      config,
    };
  }, [onUpdateArea, onUpdateGsm, onAddVictim, onUpdateVictim, onRemoveVictim, config]);

  // Search state (OpenStreetMap Nominatim Geocoding)
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchTimeoutRef = useRef(null);

  // Box Drawing state
  const isDrawingBoxRef = useRef(false);
  const boxStartLatLngRef = useRef(null);
  const tempDrawRectRef = useRef(null);

  // Area dimensions
  const areaW = parseFloat(config?.area?.area_width_m) || 4000;
  const areaH = parseFloat(config?.area?.area_height_m) || 4000;
  const originLat = parseFloat(config?.area?.origin_lat) || 50.0614;
  const originLon = parseFloat(config?.area?.origin_lon) || 19.9366;
  const totalAreaKm2 = ((areaW * areaH) / 1e6).toFixed(1);

  // Helper toast notification
  const showToast = (msg, duration = 3000) => {
    setFeedbackToast(msg);
    setTimeout(() => {
      setFeedbackToast((prev) => (prev === msg ? null : prev));
    }, duration);
  };

  // Keyboard shortcut listener: ESC to cancel tool
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && interactionModeRef.current !== "view") {
        setInteractionMode("view");
        showToast("Anulowano akcję. Tryb przeglądania mapy.");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Handle location search with Nominatim OpenStreetMap
  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (!val || val.trim().length < 2) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
            val.trim()
          )}&limit=5&countrycodes=pl,sk,cz`
        );
        if (res.ok) {
          const data = await res.json();
          setSearchResults(data);
          setShowResults(true);
        }
      } catch (err) {
        console.warn("Geocoding search failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 400);
  };

  const selectSearchResult = (item) => {
    const lat = parseFloat(item.lat);
    const lon = parseFloat(item.lon);
    if (isNaN(lat) || isNaN(lon)) return;

    if (callbacksRef.current.onUpdateArea) {
      callbacksRef.current.onUpdateArea({
        origin_lat: Math.round(lat * 10000) / 10000,
        origin_lon: Math.round(lon * 10000) / 10000,
      });
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([lat, lon], 12, { duration: 1.2 });
    }
    setSearchQuery(item.display_name.split(",")[0]);
    setShowResults(false);
    showToast(`Przeniesiono do: ${item.display_name.split(",")[0]}`);
  };

  const selectQuickLocation = (loc) => {
    if (callbacksRef.current.onUpdateArea) {
      callbacksRef.current.onUpdateArea({ origin_lat: loc.lat, origin_lon: loc.lon });
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([loc.lat, loc.lon], 12, { duration: 1.0 });
    }
    showToast(`Przeniesiono do strefy: ${loc.name}`);
  };

  // Quick Area Dimension Step Adjusters
  const adjustDimension = (dim, deltaMeters) => {
    if (isSquareLocked) {
      const curW = areaW;
      const newVal = Math.max(1000, Math.min(25000, curW + deltaMeters));
      if (callbacksRef.current.onUpdateArea) {
        callbacksRef.current.onUpdateArea({
          area_width_m: newVal,
          area_height_m: newVal,
        });
      }
      showToast(`Zmieniono rozmiar kwadratu na: ${(newVal / 1000).toFixed(1)} km`);
      return;
    }

    const curVal = dim === "width" ? areaW : areaH;
    const newVal = Math.max(1000, Math.min(25000, curVal + deltaMeters));
    if (callbacksRef.current.onUpdateArea) {
      callbacksRef.current.onUpdateArea({
        [dim === "width" ? "area_width_m" : "area_height_m"]: newVal,
      });
    }
    showToast(
      `Zmieniono ${dim === "width" ? "szerokość" : "długość"} na: ${(newVal / 1000).toFixed(1)} km`
    );
  };

  const setUniformSize = (sizeKm) => {
    const meters = Math.max(1000, Math.min(25000, sizeKm * 1000));
    if (callbacksRef.current.onUpdateArea) {
      callbacksRef.current.onUpdateArea({
        area_width_m: meters,
        area_height_m: meters,
      });
    }
    showToast(`Ustawiono strefę: ${sizeKm} × ${sizeKm} km (${sizeKm * sizeKm} km²)`);
  };

  // Fit bounds to area boundary
  const fitToBoundary = useCallback(() => {
    const map = mapInstanceRef.current;
    if (!map || !config) return;
    const area = config.area || {};
    const curLat = parseFloat(area.origin_lat) || 50.0614;
    const curLon = parseFloat(area.origin_lon) || 19.9366;
    const curW = parseFloat(area.area_width_m) || 4000.0;
    const curH = parseFloat(area.area_height_m) || 4000.0;
    const latM = 111320.0;
    const lonM = 111320.0 * Math.cos((curLat * Math.PI) / 180.0);
    const dLat = curH / 2.0 / latM;
    const dLon = curW / 2.0 / lonM;
    map.fitBounds(
      [
        [curLat + dLat, curLon - dLon],
        [curLat - dLat, curLon + dLon],
      ],
      { padding: [50, 50], maxZoom: 14 }
    );
  }, [config]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialLat = parseFloat(config?.area?.origin_lat) || 50.0614;
    const initialLon = parseFloat(config?.area?.origin_lon) || 19.9366;

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLon],
      zoom: 12,
      zoomControl: false,
      attributionControl: false,
    });
    mapInstanceRef.current = map;

    L.control.zoom({ position: "bottomright" }).addTo(map);

    // Basemap: CARTO Dark Matter
    L.tileLayer(
      `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`,
      { maxZoom: 18, subdomains: "abcd" }
    ).addTo(map);

    layersRef.current.boundary = L.layerGroup().addTo(map);
    layersRef.current.handles = L.layerGroup().addTo(map);
    layersRef.current.labels = L.layerGroup().addTo(map);
    layersRef.current.centerGrip = L.layerGroup().addTo(map);
    layersRef.current.gsmBlackout = L.layerGroup().addTo(map);
    layersRef.current.gsmTower = L.layerGroup().addTo(map);
    layersRef.current.gsmHandles = L.layerGroup().addTo(map);
    layersRef.current.gcs = L.layerGroup().addTo(map);
    layersRef.current.gcsRange = L.layerGroup().addTo(map);
    layersRef.current.victims = L.layerGroup().addTo(map);
    layersRef.current.drawTemp = L.layerGroup().addTo(map);

    // ----------------------------------------------------
    // Box-Draw & Click Handlers
    // ----------------------------------------------------
    map.on("mousedown", (e) => {
      if (interactionModeRef.current !== "box_draw") return;
      isDrawingBoxRef.current = true;
      boxStartLatLngRef.current = e.latlng;
      map.dragging.disable();

      if (tempDrawRectRef.current) {
        tempDrawRectRef.current.remove();
        tempDrawRectRef.current = null;
      }

      tempDrawRectRef.current = L.rectangle([e.latlng, e.latlng], {
        color: "#00f0ff",
        weight: 2,
        fillColor: "#00f0ff",
        fillOpacity: 0.15,
        dashArray: "4, 4",
      }).addTo(layersRef.current.drawTemp);
    });

    map.on("mousemove", (e) => {
      if (!isDrawingBoxRef.current || !boxStartLatLngRef.current || !tempDrawRectRef.current) return;
      const start = boxStartLatLngRef.current;
      const cur = e.latlng;

      const bounds = L.latLngBounds(start, cur);
      tempDrawRectRef.current.setBounds(bounds);

      // Compute live dimensions
      const midLat = (start.lat + cur.lat) / 2;
      const latM = 111320.0;
      const lonM = 111320.0 * Math.cos((midLat * Math.PI) / 180.0);
      const wM = Math.abs(cur.lng - start.lng) * lonM;
      const hM = Math.abs(cur.lat - start.lat) * latM;

      tempDrawRectRef.current.bindTooltip(
        `<div style="font-family:monospace; font-size:11px; font-weight:bold; color:#00f0ff;">
          ${(wM / 1000).toFixed(1)} km × ${(hM / 1000).toFixed(1)} km
        </div>`,
        { permanent: true, direction: "center", className: "tactical-tooltip" }
      ).openTooltip();
    });

    map.on("mouseup", (e) => {
      if (!isDrawingBoxRef.current) return;
      isDrawingBoxRef.current = false;
      map.dragging.enable();

      if (!boxStartLatLngRef.current) return;
      const start = boxStartLatLngRef.current;
      const end = e.latlng;

      const minLat = Math.min(start.lat, end.lat);
      const maxLat = Math.max(start.lat, end.lat);
      const minLon = Math.min(start.lng, end.lng);
      const maxLon = Math.max(start.lng, end.lng);

      const centerLat = (minLat + maxLat) / 2;
      const centerLon = (minLon + maxLon) / 2;

      const latM = 111320.0;
      const lonM = 111320.0 * Math.cos((centerLat * Math.PI) / 180.0);

      let wM = Math.round(Math.abs(maxLon - minLon) * lonM / 100) * 100;
      let hM = Math.round(Math.abs(maxLat - minLat) * latM / 100) * 100;

      // Clean up temp rect
      if (tempDrawRectRef.current) {
        tempDrawRectRef.current.remove();
        tempDrawRectRef.current = null;
      }
      boxStartLatLngRef.current = null;

      // Minimum threshold 300m
      if (wM < 300 || hM < 300) {
        showToast("Zaznaczony obszar był za mały (min. 500m).");
        setInteractionMode("view");
        return;
      }

      wM = Math.max(500, Math.min(25000, wM));
      hM = Math.max(500, Math.min(25000, hM));

      if (isSquareLockedRef.current) {
        const side = Math.max(wM, hM);
        wM = side;
        hM = side;
      }

      if (callbacksRef.current.onUpdateArea) {
        callbacksRef.current.onUpdateArea({
          origin_lat: Math.round(centerLat * 10000) / 10000,
          origin_lon: Math.round(centerLon * 10000) / 10000,
          area_width_m: wM,
          area_height_m: hM,
        });
      }

      setInteractionMode("view");
      showToast(
        `Zdefiniowano nową strefę: ${(wM / 1000).toFixed(1)} × ${(hM / 1000).toFixed(1)} km!`
      );
    });

    // Single-click interactions for other modes
    map.on("click", (e) => {
      const mode = interactionModeRef.current;
      if (mode === "box_draw" || mode === "view") return;

      const clickedLat = e.latlng.lat;
      const clickedLon = e.latlng.lng;
      const curConfig = callbacksRef.current.config;
      const oLat = parseFloat(curConfig?.area?.origin_lat) || 50.0614;
      const oLon = parseFloat(curConfig?.area?.origin_lon) || 19.9366;

      const latM = 111320.0;
      const lonM = 111320.0 * Math.cos((oLat * Math.PI) / 180.0);

      if (mode === "edit_gsm") {
        const offX = Math.round((clickedLon - oLon) * lonM);
        const offY = Math.round((clickedLat - oLat) * latM);
        if (callbacksRef.current.onUpdateGsm) {
          callbacksRef.current.onUpdateGsm({
            center_offset_x_m: offX,
            center_offset_y_m: offY,
          });
        }
        showToast(`Przeniesiono epicentrum awarii GSM: (${offX}m, ${offY}m)`);
        return;
      } else if (mode === "set_center") {
        if (callbacksRef.current.onUpdateArea) {
          callbacksRef.current.onUpdateArea({
            origin_lat: Math.round(clickedLat * 10000) / 10000,
            origin_lon: Math.round(clickedLon * 10000) / 10000,
          });
        }
        showToast("Przeniesiono centrum strefy.");
        setInteractionMode("view");
      } else if (mode === "set_gcs") {
        const offX = Math.round((clickedLon - oLon) * lonM);
        const offY = Math.round((clickedLat - oLat) * latM);
        if (callbacksRef.current.onUpdateArea) {
          callbacksRef.current.onUpdateArea({
            gcs_offset_x_m: offX,
            gcs_offset_y_m: offY,
          });
        }
        showToast("Zaktualizowano pozycję bazy GCS.");
        setInteractionMode("view");
      } else if (mode === "add_victim") {
        const localX = Math.round((clickedLon - oLon) * lonM);
        const localY = Math.round((clickedLat - oLat) * latM);
        const randMac = `02:00:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(
          Math.random() * 89 + 10
        )}:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(Math.random() * 89 + 10)}`;

        if (callbacksRef.current.onAddVictim) {
          callbacksRef.current.onAddVictim({
            local_x: localX,
            local_y: localY,
            mac: randMac,
            signal_type: victimSignalTypeRef.current || "WIFI_PROBE_REQ",
            tx_power_dbm: victimSignalTypeRef.current === "LTE_DIRECT_UPLINK" ? 22.0 : 16.0,
            burst_interval_sec: 5.0,
          });
        }
        showToast("Dodano nową ofiarę na mapie!");
      }
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update map container cursor and dragging state when interactionMode changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapContainerRef.current) return;

    if (interactionMode === "box_draw") {
      mapContainerRef.current.style.cursor = "crosshair";
      map.dragging.disable();
    } else if (interactionMode === "set_center" || interactionMode === "set_gcs" || interactionMode === "add_victim") {
      mapContainerRef.current.style.cursor = "crosshair";
      map.dragging.enable();
    } else {
      mapContainerRef.current.style.cursor = "";
      map.dragging.enable();
    }
  }, [interactionMode]);

  // Keep map container responsive on window resize
  useEffect(() => {
    if (!mapContainerRef.current) return;
    const ro = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    });
    ro.observe(mapContainerRef.current);
    return () => ro.disconnect();
  }, []);

  // ----------------------------------------------------
  // Render Map Features & Interactive Grips when config changes
  // ----------------------------------------------------
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !config) return;

    const area = config.area || {};
    const mesh = config.mesh || {};
    const victims = config.victims || [];

    const curOriginLat = parseFloat(area.origin_lat) || 50.0614;
    const curOriginLon = parseFloat(area.origin_lon) || 19.9366;
    let widthM = parseFloat(area.area_width_m) || 4000.0;
    let heightM = parseFloat(area.area_height_m) || 4000.0;
    const gcsOffX = parseFloat(area.gcs_offset_x_m) || -650.0;
    const gcsOffY = parseFloat(area.gcs_offset_y_m) || -650.0;
    const gcsRangeM = parseFloat(mesh.gcs_range_m) || 5000.0;

    const latM = 111320.0;
    const lonM = 111320.0 * Math.cos((curOriginLat * Math.PI) / 180.0);

    const dLat = heightM / 2.0 / latM;
    const dLon = widthM / 2.0 / lonM;

    const boundaryCoords = [
      [curOriginLat + dLat, curOriginLon - dLon], // NW
      [curOriginLat + dLat, curOriginLon + dLon], // NE
      [curOriginLat - dLat, curOriginLon + dLon], // SE
      [curOriginLat - dLat, curOriginLon - dLon], // SW
    ];

    // Smoothly fly camera to new preset coordinates when scenario changes
    const centerKey = `${curOriginLat.toFixed(3)}_${curOriginLon.toFixed(3)}`;
    if (lastPresetCenterRef.current && lastPresetCenterRef.current !== centerKey) {
      map.invalidateSize();
      map.flyToBounds(
        [
          [curOriginLat + dLat, curOriginLon - dLon],
          [curOriginLat - dLat, curOriginLon + dLon],
        ],
        { padding: [60, 60], duration: 1.0, maxZoom: 14 }
      );
    }
    lastPresetCenterRef.current = centerKey;

    // 1. Boundary Polygon
    const boundaryLayer = layersRef.current.boundary;
    boundaryLayer.clearLayers();

    const boundaryPoly = L.polygon(boundaryCoords, {
      color: "#00f0ff",
      weight: 2.2,
      fillColor: "#00f0ff",
      fillOpacity: 0.08,
      dashArray: "6, 6",
    }).addTo(boundaryLayer);

    boundaryPoly.bindTooltip(
      `<div style="font-family:monospace; font-size:11px;">
        <b style="color:#00f0ff;">Strefa Poszukiwawcza SAR</b><br>
        Szerokość: <b>${(widthM / 1000).toFixed(1)} km</b> | Długość: <b>${(heightM / 1000).toFixed(1)} km</b><br>
        Powierzchnia: <b>${((widthM * heightM) / 1e6).toFixed(1)} km²</b><br>
        <span style="color:#94a3b8; font-size:10px;">Chwyć narożnik lub krawędź, aby rozciągnąć</span>
      </div>`,
      { sticky: true }
    );

    // 2. Central Drag Grip Badge (Move the whole zone)
    const isGsmMode = interactionModeRef.current === "edit_gsm";
    const centerGripLayer = layersRef.current.centerGrip;
    centerGripLayer.clearLayers();

    const centerGripIcon = L.divIcon({
      className: "center-zone-grip",
      html: `
        <div style="display:flex; flex-direction:column; align-items:center; transform:translate(-50%, -100%); cursor:${isGsmMode ? "default" : "move"}; opacity:${isGsmMode ? 0.35 : 1.0}; pointer-events:${isGsmMode ? "none" : "auto"};">
          <div style="display:flex; align-items:center; gap:5px; background:rgba(9,13,22,0.95); border:1.5px solid #00f0ff; border-radius:20px; padding:3px 9px; box-shadow:0 0 16px rgba(0,240,255,0.7); white-space:nowrap;">
            <div style="width:7px; height:7px; border-radius:50%; background:#00f0ff; box-shadow:0 0 8px #00f0ff; animation:pulse 2s infinite;"></div>
            <span style="font-family:monospace; font-size:9.5px; font-weight:800; color:#00f0ff; letter-spacing:0.5px;">CENTRUM SAR</span>
            <span style="font-family:monospace; font-size:9px; color:#94a3b8; border-left:1px solid rgba(255,255,255,0.2); padding-left:4px;">${((widthM * heightM) / 1e6).toFixed(1)} km²</span>
          </div>
          <div style="width:1.5px; height:8px; background:#00f0ff; box-shadow:0 0 6px #00f0ff;"></div>
          <div style="width:6px; height:6px; border-radius:50%; background:#00f0ff; border:1px solid #fff;"></div>
        </div>
      `,
      iconSize: [0, 0],
    });

    const centerMarker = L.marker([curOriginLat, curOriginLon], {
      icon: centerGripIcon,
      draggable: !isGsmMode,
      zIndexOffset: isGsmMode ? 100 : 1000,
    }).addTo(centerGripLayer);

    centerMarker.bindTooltip(
      `<div style="font-family:monospace; font-size:10.5px;">
        <b style="color:#00f0ff;">Środek Strefy SAR</b><br>
        Przeciągnij w dowolne miejsce, aby przesunąć cały rejon poszukiwań.
      </div>`,
      { sticky: true }
    );

    centerMarker.on("drag", (e) => {
      const pos = e.latlng;
      boundaryPoly.setLatLngs([
        [pos.lat + dLat, pos.lng - dLon],
        [pos.lat + dLat, pos.lng + dLon],
        [pos.lat - dLat, pos.lng + dLon],
        [pos.lat - dLat, pos.lng - dLon],
      ]);
    });

    centerMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      lastPresetCenterRef.current = `${pos.lat.toFixed(3)}_${pos.lng.toFixed(3)}`;
      if (callbacksRef.current.onUpdateArea) {
        callbacksRef.current.onUpdateArea({
          origin_lat: Math.round(pos.lat * 10000) / 10000,
          origin_lon: Math.round(pos.lng * 10000) / 10000,
        });
      }
      showToast(`Przeniesiono centrum strefy do: ${pos.lat.toFixed(4)}°N, ${pos.lng.toFixed(4)}°E`);
    });

    // 3. Dynamic Dimension Labels on Edges
    const labelsLayer = layersRef.current.labels;
    labelsLayer.clearLayers();

    // Top edge width label
    const topLabelIcon = L.divIcon({
      className: "edge-dimension-label",
      html: `
        <div style="background:rgba(9,13,22,0.85); border:1px solid rgba(0,240,255,0.6); color:#00f0ff; padding:2px 8px; border-radius:12px; font-family:monospace; font-size:10px; font-weight:bold; box-shadow:0 2px 8px rgba(0,0,0,0.8); transform:translate(-50%, -120%); pointer-events:none; white-space:nowrap;">
          ↔ Szerokość: ${(widthM / 1000).toFixed(1)} km
        </div>
      `,
      iconSize: [0, 0],
    });
    L.marker([curOriginLat + dLat, curOriginLon], {
      icon: topLabelIcon,
      interactive: false,
    }).addTo(labelsLayer);

    // Right edge height label
    const rightLabelIcon = L.divIcon({
      className: "edge-dimension-label",
      html: `
        <div style="background:rgba(9,13,22,0.85); border:1px solid rgba(0,240,255,0.6); color:#00f0ff; padding:2px 8px; border-radius:12px; font-family:monospace; font-size:10px; font-weight:bold; box-shadow:0 2px 8px rgba(0,0,0,0.8); transform:translate(20%, -50%); pointer-events:none; white-space:nowrap;">
          ↕ Długość: ${(heightM / 1000).toFixed(1)} km
        </div>
      `,
      iconSize: [0, 0],
    });
    L.marker([curOriginLat, curOriginLon + dLon], {
      icon: rightLabelIcon,
      interactive: false,
    }).addTo(labelsLayer);

    // 4. Interactive Live Handles for Boundary Resizing (Corners + Midpoints)
    const handlesLayer = layersRef.current.handles;
    handlesLayer.clearLayers();

    const createCornerHandle = (lat, lon, cursor, name) => {
      const handleIcon = L.divIcon({
        className: "boundary-resize-corner",
        html: `
          <div style="width:26px; height:26px; display:flex; align-items:center; justify-content:center; cursor:${cursor}; transform:translate(-13px, -13px);">
            <div style="width:16px; height:16px; background:#00f0ff; border:2.5px solid #ffffff; border-radius:4px; box-shadow:0 0 12px rgba(0,240,255,0.9); display:flex; align-items:center; justify-content:center; transition:transform 0.15s ease;">
              <div style="width:4px; height:4px; background:#000000; border-radius:1px;"></div>
            </div>
          </div>
        `,
        iconSize: [0, 0],
      });

      const marker = L.marker([lat, lon], {
        icon: handleIcon,
        draggable: true,
        zIndexOffset: 500,
      }).addTo(handlesLayer);

      marker.bindTooltip(
        `<div style="font-family:monospace; font-size:10px;">
          <b>Narożnik ${name}</b><br>Przeciągnij, aby zmienić rozmiar
        </div>`,
        { sticky: true }
      );

      marker.on("drag", (e) => {
        const pos = e.latlng;
        let newW = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lng - curOriginLon) * 2 * lonM / 200) * 200));
        let newH = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lat - curOriginLat) * 2 * latM / 200) * 200));

        if (isSquareLockedRef.current) {
          const side = Math.max(newW, newH);
          newW = side;
          newH = side;
        }

        const newDLat = newH / 2.0 / latM;
        const newDLon = newW / 2.0 / lonM;

        boundaryPoly.setLatLngs([
          [curOriginLat + newDLat, curOriginLon - newDLon],
          [curOriginLat + newDLat, curOriginLon + newDLon],
          [curOriginLat - newDLat, curOriginLon + newDLon],
          [curOriginLat - newDLat, curOriginLon - newDLon],
        ]);

        marker.setTooltipContent(
          `<b>Rozmiar:</b> ${(newW / 1000).toFixed(1)} × ${(newH / 1000).toFixed(1)} km (${((newW * newH) / 1e6).toFixed(1)} km²)`
        );
      });

      marker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        let newW = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lng - curOriginLon) * 2 * lonM / 200) * 200));
        let newH = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lat - curOriginLat) * 2 * latM / 200) * 200));

        if (isSquareLockedRef.current) {
          const side = Math.max(newW, newH);
          newW = side;
          newH = side;
        }

        if (callbacksRef.current.onUpdateArea) {
          callbacksRef.current.onUpdateArea({
            area_width_m: newW,
            area_height_m: newH,
          });
        }
        showToast(`Nowy rozmiar strefy: ${(newW / 1000).toFixed(1)} × ${(newH / 1000).toFixed(1)} km`);
      });

      return marker;
    };

    createCornerHandle(curOriginLat + dLat, curOriginLon - dLon, "nwse-resize", "NW");
    createCornerHandle(curOriginLat + dLat, curOriginLon + dLon, "nesw-resize", "NE");
    createCornerHandle(curOriginLat - dLat, curOriginLon + dLon, "nwse-resize", "SE");
    createCornerHandle(curOriginLat - dLat, curOriginLon - dLon, "nesw-resize", "SW");

    // 4 Midpoint Edge Grips
    const createEdgeHandle = (lat, lon, isVertical, edgeName) => {
      const edgeIcon = L.divIcon({
        className: "boundary-resize-edge",
        html: `
          <div style="display:flex; align-items:center; justify-content:center; cursor:${isVertical ? "ns-resize" : "ew-resize"}; transform:translate(-50%, -50%);">
            <div style="width:${isVertical ? "28px" : "10px"}; height:${isVertical ? "10px" : "28px"}; background:rgba(0,240,255,0.9); border:2px solid #ffffff; border-radius:4px; box-shadow:0 0 10px rgba(0,240,255,0.85);"></div>
          </div>
        `,
        iconSize: [0, 0],
      });

      const marker = L.marker([lat, lon], {
        icon: edgeIcon,
        draggable: true,
        zIndexOffset: 450,
      }).addTo(handlesLayer);

      marker.bindTooltip(
        `<div style="font-family:monospace; font-size:10px;">
          <b>Krawędź ${edgeName}</b><br>Przeciągnij, aby zmienić ${isVertical ? "długość" : "szerokość"}
        </div>`,
        { sticky: true }
      );

      marker.on("drag", (e) => {
        const pos = e.latlng;
        if (isVertical) {
          let newH = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lat - curOriginLat) * 2 * latM / 200) * 200));
          let newW = widthM;
          if (isSquareLockedRef.current) {
            newW = newH;
          }
          const newDLat = newH / 2.0 / latM;
          const newDLon = newW / 2.0 / lonM;
          boundaryPoly.setLatLngs([
            [curOriginLat + newDLat, curOriginLon - newDLon],
            [curOriginLat + newDLat, curOriginLon + newDLon],
            [curOriginLat - newDLat, curOriginLon + newDLon],
            [curOriginLat - newDLat, curOriginLon - newDLon],
          ]);
          marker.setTooltipContent(`<b>Długość:</b> ${(newH / 1000).toFixed(1)} km`);
        } else {
          let newW = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lng - curOriginLon) * 2 * lonM / 200) * 200));
          let newH = heightM;
          if (isSquareLockedRef.current) {
            newH = newW;
          }
          const newDLat = newH / 2.0 / latM;
          const newDLon = newW / 2.0 / lonM;
          boundaryPoly.setLatLngs([
            [curOriginLat + newDLat, curOriginLon - newDLon],
            [curOriginLat + newDLat, curOriginLon + newDLon],
            [curOriginLat - newDLat, curOriginLon + newDLon],
            [curOriginLat - newDLat, curOriginLon - newDLon],
          ]);
          marker.setTooltipContent(`<b>Szerokość:</b> ${(newW / 1000).toFixed(1)} km`);
        }
      });

      marker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        if (isVertical) {
          let newH = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lat - curOriginLat) * 2 * latM / 200) * 200));
          const updates = { area_height_m: newH };
          if (isSquareLockedRef.current) updates.area_width_m = newH;
          if (callbacksRef.current.onUpdateArea) {
            callbacksRef.current.onUpdateArea(updates);
          }
          showToast(`Nowa długość: ${(newH / 1000).toFixed(1)} km`);
        } else {
          let newW = Math.max(1000, Math.min(25000, Math.round(Math.abs(pos.lng - curOriginLon) * 2 * lonM / 200) * 200));
          const updates = { area_width_m: newW };
          if (isSquareLockedRef.current) updates.area_height_m = newW;
          if (callbacksRef.current.onUpdateArea) {
            callbacksRef.current.onUpdateArea(updates);
          }
          showToast(`Nowa szerokość: ${(newW / 1000).toFixed(1)} km`);
        }
      });
    };

    createEdgeHandle(curOriginLat + dLat, curOriginLon, true, "Północna");
    createEdgeHandle(curOriginLat - dLat, curOriginLon, true, "Południowa");
    createEdgeHandle(curOriginLat, curOriginLon + dLon, false, "Wschodnia");
    createEdgeHandle(curOriginLat, curOriginLon - dLon, false, "Zachodnia");

    // 5. GCS Base Station & C2 Radio Range Circle
    const gcsLat = curOriginLat + gcsOffY / latM;
    const gcsLon = curOriginLon + gcsOffX / lonM;

    const gcsLayer = layersRef.current.gcs;
    const gcsRangeLayer = layersRef.current.gcsRange;
    gcsLayer.clearLayers();
    gcsRangeLayer.clearLayers();

    const gcsIcon = L.divIcon({
      className: "gcs-preview-marker",
      html: `
        <div style="display:flex; flex-direction:column; align-items:center; cursor:move; transform:translate(-50%, -50%);">
          <div style="width:28px; height:28px; background:#10b981; border:2px solid #ffffff; border-radius:6px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 14px rgba(16,185,129,0.9);">
            <span style="font-size:12px; font-weight:900; color:#000; font-family:monospace;">G</span>
          </div>
          <div style="font-family:monospace; font-size:9.5px; font-weight:700; color:#10b981; background:rgba(0,0,0,0.8); padding:0 4px; border-radius:3px; margin-top:2px; text-shadow:0 0 4px #000;">GCS BASE</div>
        </div>
      `,
      iconSize: [0, 0],
    });

    const gcsMarker = L.marker([gcsLat, gcsLon], {
      icon: gcsIcon,
      draggable: true,
      zIndexOffset: 900,
    }).addTo(gcsLayer);

    gcsMarker.bindTooltip(
      `<div style="font-family:monospace; font-size:10px;">
        <b style="color:#10b981;">Baza Naziemna GCS</b><br>
        Offset: (${gcsOffX}m, ${gcsOffY}m)<br>
        Przeciągnij, aby zmienić lokalizację masztu C2
      </div>`,
      { sticky: true }
    );

    gcsMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      const offX = Math.round((pos.lng - curOriginLon) * lonM);
      const offY = Math.round((pos.lat - curOriginLat) * latM);
      if (callbacksRef.current.onUpdateArea) {
        callbacksRef.current.onUpdateArea({
          gcs_offset_x_m: offX,
          gcs_offset_y_m: offY,
        });
      }
      showToast(`Przesunięto bazę GCS: (${offX}m, ${offY}m) od centrum.`);
    });

    L.circle([gcsLat, gcsLon], {
      radius: gcsRangeM,
      color: "#ffb700",
      weight: 1.5,
      dashArray: "6, 6",
      fillColor: "#ffb700",
      fillOpacity: 0.04,
    })
      .bindTooltip(`<b>Zasięg Masztu GCS:</b> ${(gcsRangeM / 1000).toFixed(1)} km`, { sticky: true })
      .addTo(gcsRangeLayer);

    // ----------------------------------------------------
    // 5b. GSM Blackout Infrastructure & Surviving Macro BTS
    // ----------------------------------------------------
    const gsm = config.gsm || {};
    const centerOffX = parseFloat(gsm.center_offset_x_m) || 0.0;
    const centerOffY = parseFloat(gsm.center_offset_y_m) || 0.0;
    const defaultBlackoutRadius = Math.max(widthM, heightM) * 0.65;
    const blackoutRadiusM =
      parseFloat(gsm.blackout_radius_m) > 0 ? parseFloat(gsm.blackout_radius_m) : defaultBlackoutRadius;
    const towerOffsetM = parseFloat(gsm.tower_offset_m) || 1500.0;
    const normalRssi = parseFloat(gsm.normal_rssi_dbm) || -65.0;
    const blackoutRssi = parseFloat(gsm.blackout_rssi_dbm) || -118.0;

    const blackoutCenterLat = curOriginLat + centerOffY / latM;
    const blackoutCenterLon = curOriginLon + centerOffX / lonM;

    // Tower Coordinates
    let towerX = gsm.tower_offset_x_m != null ? parseFloat(gsm.tower_offset_x_m) : -widthM / 2 - towerOffsetM * 0.4;
    let towerY = gsm.tower_offset_y_m != null ? parseFloat(gsm.tower_offset_y_m) : -heightM / 2 - towerOffsetM * 0.4;
    const towerLat = curOriginLat + towerY / latM;
    const towerLon = curOriginLon + towerX / lonM;
    const towerDistToCrisis = Math.round(Math.hypot(towerX - centerOffX, towerY - centerOffY));

    const gsmBlackoutLayer = layersRef.current.gsmBlackout;
    const gsmTowerLayer = layersRef.current.gsmTower;
    const gsmHandlesLayer = layersRef.current.gsmHandles;

    gsmBlackoutLayer.clearLayers();
    gsmTowerLayer.clearLayers();
    gsmHandlesLayer.clearLayers();

    // 1. Blackout Circles: Outer degradation zone (amber) + Inner complete blackout zone (red)
    const outerCircle = L.circle([blackoutCenterLat, blackoutCenterLon], {
      radius: blackoutRadiusM,
      color: "#f59e0b",
      weight: isGsmMode ? 2.5 : 1.5,
      dashArray: "5, 6",
      fillColor: "#f59e0b",
      fillOpacity: isGsmMode ? 0.12 : 0.05,
    }).addTo(gsmBlackoutLayer);

    const innerRadiusM = blackoutRadiusM * 0.65;
    const innerCircle = L.circle([blackoutCenterLat, blackoutCenterLon], {
      radius: innerRadiusM,
      color: "#ef4444",
      weight: isGsmMode ? 2.5 : 1.8,
      dashArray: "6, 6",
      fillColor: "#ef4444",
      fillOpacity: isGsmMode ? 0.22 : 0.09,
    }).addTo(gsmBlackoutLayer);

    // Clicking inside circles in edit_gsm mode moves the blackout center
    innerCircle.on("click", (e) => {
      if (interactionModeRef.current === "edit_gsm") {
        L.DomEvent.stopPropagation(e);
        const pos = e.latlng;
        const offX = Math.round((pos.lng - curOriginLon) * lonM);
        const offY = Math.round((pos.lat - curOriginLat) * latM);
        if (callbacksRef.current.onUpdateGsm) {
          callbacksRef.current.onUpdateGsm({
            center_offset_x_m: offX,
            center_offset_y_m: offY,
          });
        }
        showToast(`Przeniesiono epicentrum awarii GSM: (${offX}m, ${offY}m)`);
      }
    });

    outerCircle.bindTooltip(
      `<div style="font-family:monospace; font-size:11px;">
        <b style="color:#ef4444;">🚨 Strefa Awarii GSM (Blackout)</b><br>
        Promień całkowity: <b>${(blackoutRadiusM / 1000).toFixed(1)} km</b> (${((Math.PI * blackoutRadiusM * blackoutRadiusM) / 1e6).toFixed(1)} km²)<br>
        Sygnał w centrum: <b>${blackoutRssi} dBm (Brak Sieci)</b><br>
        <span style="color:#f59e0b; font-size:10px;">Zanik łączności komórkowej w rejonie katastrofy</span>
      </div>`,
      { sticky: true }
    );

    // 2. Blackout Epicenter Drag Marker (Positioned below center point with pin upwards)
    const blackoutGripIcon = L.divIcon({
      className: "gsm-epicenter-marker",
      html: `
        <div style="display:flex; flex-direction:column; align-items:center; transform:translate(-50%, 0); cursor:move;">
          <div style="width:6px; height:6px; border-radius:50%; background:#ef4444; border:1px solid #fff;"></div>
          <div style="width:1.5px; height:8px; background:#ef4444; box-shadow:0 0 6px #ef4444;"></div>
          <div style="display:flex; align-items:center; gap:5px; background:rgba(20,5,10,0.95); border:1.5px solid #ef4444; border-radius:20px; padding:3px 9px; box-shadow:0 0 18px rgba(239,68,68,0.9); white-space:nowrap;">
            <div style="width:7px; height:7px; border-radius:50%; background:#ef4444; box-shadow:0 0 8px #ef4444; animation:pulse 1.8s infinite;"></div>
            <span style="font-family:monospace; font-size:10px; font-weight:800; color:#ef4444; letter-spacing:0.5px;">AWARIA GSM</span>
            <span style="font-family:monospace; font-size:9px; color:#fca5a5; border-left:1px solid rgba(255,255,255,0.2); padding-left:4px;">${(blackoutRadiusM / 1000).toFixed(1)} km</span>
          </div>
        </div>
      `,
      iconSize: [0, 0],
    });

    const blackoutMarker = L.marker([blackoutCenterLat, blackoutCenterLon], {
      icon: blackoutGripIcon,
      draggable: true,
      zIndexOffset: isGsmMode ? 3500 : 1500,
    }).addTo(gsmHandlesLayer);

    blackoutMarker.bindTooltip(
      `<div style="font-family:monospace; font-size:10px;">
        <b style="color:#ef4444;">Epicentrum Awarii GSM</b><br>
        Przeciągnij, aby przesunąć środek strefy blackoutu.
      </div>`,
      { sticky: true }
    );

    blackoutMarker.on("drag", (e) => {
      const pos = e.latlng;
      outerCircle.setLatLng(pos);
      innerCircle.setLatLng(pos);
    });

    blackoutMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      const offX = Math.round((pos.lng - curOriginLon) * lonM);
      const offY = Math.round((pos.lat - curOriginLat) * latM);
      if (callbacksRef.current.onUpdateGsm) {
        callbacksRef.current.onUpdateGsm({
          center_offset_x_m: offX,
          center_offset_y_m: offY,
        });
      }
      showToast(`Przesunięto centrum awarii GSM: (${offX}m, ${offY}m)`);
    });

    // 3. Blackout Radius Handle (on edge of outer circle)
    const radiusHandleLat = blackoutCenterLat;
    const radiusHandleLon = blackoutCenterLon + blackoutRadiusM / lonM;

    const radiusHandleIcon = L.divIcon({
      className: "gsm-radius-handle",
      html: `
        <div style="width:24px; height:24px; display:flex; align-items:center; justify-content:center; cursor:ew-resize; transform:translate(-12px, -12px);">
          <div style="width:14px; height:14px; background:#f59e0b; border:2px solid #ffffff; border-radius:50%; box-shadow:0 0 10px rgba(245,158,11,0.9); display:flex; align-items:center; justify-content:center;">
            <div style="width:4px; height:4px; background:#000000; border-radius:50%;"></div>
          </div>
        </div>
      `,
      iconSize: [0, 0],
    });

    const radiusMarker = L.marker([radiusHandleLat, radiusHandleLon], {
      icon: radiusHandleIcon,
      draggable: true,
      zIndexOffset: 750,
    }).addTo(gsmHandlesLayer);

    radiusMarker.bindTooltip(
      `<div style="font-family:monospace; font-size:10px;">
        <b style="color:#f59e0b;">Zasięg Awarii GSM</b><br>
        Przeciągnij uchwyt, aby zmienić promień blackoutu.
      </div>`,
      { sticky: true }
    );

    radiusMarker.on("drag", (e) => {
      const pos = e.latlng;
      const dX = (pos.lng - blackoutCenterLon) * lonM;
      const dY = (pos.lat - blackoutCenterLat) * latM;
      const newRadius = Math.max(500, Math.min(30000, Math.round(Math.hypot(dX, dY))));
      outerCircle.setRadius(newRadius);
      innerCircle.setRadius(newRadius * 0.65);
      radiusMarker.setTooltipContent(
        `<b>Promień awarii:</b> ${(newRadius / 1000).toFixed(1)} km (${((Math.PI * newRadius * newRadius) / 1e6).toFixed(1)} km²)`
      );
    });

    radiusMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      const dX = (pos.lng - blackoutCenterLon) * lonM;
      const dY = (pos.lat - blackoutCenterLat) * latM;
      const newRadius = Math.max(500, Math.min(30000, Math.round(Math.hypot(dX, dY) / 100) * 100));
      if (callbacksRef.current.onUpdateGsm) {
        callbacksRef.current.onUpdateGsm({
          blackout_radius_m: newRadius,
        });
      }
      showToast(`Zmieniono promień awarii GSM: ${(newRadius / 1000).toFixed(1)} km`);
    });

    // 6. Victim Emitters (Draggable & Interactive with Actions)
    const victimsLayer = layersRef.current.victims;
    victimsLayer.clearLayers();

    victims.forEach((v, idx) => {
      const vLat = curOriginLat + (parseFloat(v.local_y) || 0) / latM;
      const vLon = curOriginLon + (parseFloat(v.local_x) || 0) / lonM;
      const isWifi = v.signal_type === "WIFI_PROBE_REQ";

      const vIcon = L.divIcon({
        className: "victim-preview-marker",
        html: `
          <div style="position:relative; width:28px; height:28px; display:flex; align-items:center; justify-content:center; cursor:move; transform:translate(-14px, -14px);">
            <div style="position:absolute; width:26px; height:26px; border-radius:50%; border:2px solid #ff3366; background:rgba(255,51,102,0.25); animation:pulse 2s infinite;"></div>
            <div style="width:18px; height:18px; background:#ff3366; border:2px solid #ffffff; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px rgba(255,51,102,0.9); z-index:2;">
              <span style="font-size:10px; color:#ffffff; font-weight:bold; font-family:monospace;">${idx + 1}</span>
            </div>
          </div>
        `,
        iconSize: [0, 0],
      });

      const vMarker = L.marker([vLat, vLon], {
        icon: vIcon,
        draggable: true,
        zIndexOffset: 800,
      }).addTo(victimsLayer);

      vMarker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        const newLocalX = Math.round((pos.lng - curOriginLon) * lonM);
        const newLocalY = Math.round((pos.lat - curOriginLat) * latM);
        if (callbacksRef.current.onUpdateVictim) {
          callbacksRef.current.onUpdateVictim(idx, {
            local_x: newLocalX,
            local_y: newLocalY,
          });
        }
        showToast(`Przesunięto Ofiarę #${idx + 1}: (${newLocalX}m, ${newLocalY}m)`);
      });

      // Custom Interactive Popup for Victim
      const popupDiv = document.createElement("div");
      popupDiv.style.fontFamily = "monospace";
      popupDiv.style.fontSize = "11px";
      popupDiv.style.padding = "2px";
      popupDiv.innerHTML = `
        <div style="margin-bottom:6px;">
          <b style="color:#ff3366; font-size:12px;">Ofiara #${idx + 1}</b><br>
          MAC: <b style="color:#fff;">${v.mac || "Brak"}</b><br>
          Typ sygnału: <b>${isWifi ? "Wi-Fi Probe Req (2.4 GHz)" : "LTE Direct Uplink"}</b><br>
          Pozycja lokalna: <b>(${Math.round(v.local_x)}m, ${Math.round(v.local_y)}m)</b><br>
          Moc TX: <b>${v.tx_power_dbm} dBm</b>
        </div>
        <div style="display:flex; gap:6px; margin-top:6px; border-top:1px solid rgba(255,255,255,0.15); padding-top:6px;">
          <button id="del-victim-${idx}" style="background:#ef4444; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:10px; font-weight:bold;">
            🗑️ Usuń ofiarę
          </button>
          <button id="toggle-type-${idx}" style="background:#3b82f6; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:10px; font-weight:bold;">
            ⇄ ${isWifi ? "Zmień na LTE" : "Zmień na Wi-Fi"}
          </button>
        </div>
      `;

      vMarker.bindPopup(popupDiv);
      vMarker.on("popupopen", () => {
        const delBtn = document.getElementById(`del-victim-${idx}`);
        const toggleBtn = document.getElementById(`toggle-type-${idx}`);

        if (delBtn) {
          delBtn.onclick = () => {
            vMarker.closePopup();
            if (callbacksRef.current.onRemoveVictim) {
              callbacksRef.current.onRemoveVictim(idx);
            }
          };
        }
        if (toggleBtn) {
          toggleBtn.onclick = () => {
            vMarker.closePopup();
            if (callbacksRef.current.onUpdateVictim) {
              callbacksRef.current.onUpdateVictim(idx, {
                signal_type: isWifi ? "LTE_DIRECT_UPLINK" : "WIFI_PROBE_REQ",
                tx_power_dbm: isWifi ? 22.0 : 16.0,
              });
            }
          };
        }
      });
    });
  }, [config, interactionMode]);

  return (
    <div className="relative w-full h-full min-h-[380px] flex flex-col rounded-xl overflow-hidden border border-border/50 bg-[#090d16] shadow-2xl select-none font-sans">
      {/* 1. TOP UNIFIED CLEAN BAR: Search & Action Toolbar */}
      <div className="absolute top-3 left-3 right-3 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-auto">
        {/* Geocoding Search Input (Compact & Elegant) */}
        <div className="relative w-full sm:w-72 md:w-80">
          <div className="flex items-center bg-card/90 backdrop-blur-md border border-border/80 rounded-lg px-3 py-1.5 shadow-lg transition-all focus-within:border-cyan-500/80 focus-within:ring-1 focus-within:ring-cyan-500/50">
            <Search className="w-4 h-4 text-cyan-400 shrink-0 mr-2" />
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Szukaj miejscowości (np. Zakopane)..."
              className="w-full bg-transparent border-none text-xs text-foreground placeholder:text-muted-foreground/70 outline-none"
            />
            {isSearching && (
              <div className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin shrink-0" />
            )}
            {searchQuery && !isSearching && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setSearchResults([]);
                  setShowResults(false);
                }}
                className="text-muted-foreground hover:text-foreground shrink-0 ml-1 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Search Results Dropdown */}
          {showResults && searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-card/95 backdrop-blur-md border border-border/80 rounded-lg shadow-2xl overflow-hidden z-30 text-xs">
              {searchResults.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => selectSearchResult(item)}
                  className="w-full text-left px-3 py-2 border-b border-border/40 last:border-none hover:bg-cyan-950/40 hover:text-cyan-300 transition-colors flex items-center justify-between"
                >
                  <span className="truncate pr-2">{item.display_name}</span>
                  <Badge variant="outline" className="text-[10px] shrink-0 text-cyan-400 border-cyan-500/40">
                    Wybierz
                  </Badge>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Clean Action Toolbar Pill */}
        <div className="flex items-center gap-1 bg-card/90 backdrop-blur-md border border-border/80 p-1 rounded-lg shadow-lg">
          {/* Tool: Move / View */}
          <button
            onClick={() => setInteractionMode("view")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              interactionMode === "view"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
            }`}
            title="Tryb przesuwania (przeciągaj mapę lub środek strefy)"
          >
            <Navigation className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden md:inline">Przesuwaj</span>
          </button>

          {/* Tool: Add Victim */}
          <button
            onClick={() => {
              if (interactionMode === "add_victim") {
                setInteractionMode("view");
              } else {
                setInteractionMode("add_victim");
                showToast("Kliknij w dowolne miejsce na mapie, aby dodać poszukiwaną osobę.");
              }
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              interactionMode === "add_victim"
                ? "bg-rose-600 text-white shadow-[0_0_12px_rgba(255,51,102,0.5)] animate-pulse"
                : "text-rose-400 hover:text-rose-300 hover:bg-rose-950/30"
            }`}
            title="Kliknij na mapie, aby postawić nową ofiarę"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>+ Ofiara</span>
          </button>

          {/* Victim Signal Type Pill (when adding victim) */}
          {interactionMode === "add_victim" && (
            <div className="flex items-center gap-0.5 bg-background/90 rounded border border-rose-500/50 p-0.5">
              <button
                onClick={() => setVictimSignalType("WIFI_PROBE_REQ")}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                  victimSignalType === "WIFI_PROBE_REQ"
                    ? "bg-cyan-500/30 text-cyan-300"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Wi-Fi
              </button>
              <button
                onClick={() => setVictimSignalType("LTE_DIRECT_UPLINK")}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                  victimSignalType === "LTE_DIRECT_UPLINK"
                    ? "bg-amber-500/30 text-amber-300"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                LTE
              </button>
            </div>
          )}

          {/* Tool: GCS Base */}
          <button
            onClick={() => {
              if (interactionMode === "set_gcs") {
                setInteractionMode("view");
              } else {
                setInteractionMode("set_gcs");
                showToast("Kliknij na mapie, aby przestawić bazę masztu GCS.");
              }
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              interactionMode === "set_gcs"
                ? "bg-emerald-600 text-white shadow-[0_0_12px_rgba(16,185,129,0.5)]"
                : "text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/30"
            }`}
            title="Przestaw bazę masztu GCS"
          >
            <Building className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Baza GCS</span>
          </button>

          {/* Tool: GSM Blackout Zone */}
          <button
            onClick={() => {
              if (interactionMode === "edit_gsm") {
                setInteractionMode("view");
              } else {
                setInteractionMode("edit_gsm");
                showToast("Tryb edycji GSM: Przeciągnij epicentrum awarii lub uchwyt promienia.");
              }
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              interactionMode === "edit_gsm"
                ? "bg-rose-600 text-white shadow-[0_0_12px_rgba(239,68,68,0.5)]"
                : "text-rose-400 hover:text-rose-300 hover:bg-rose-950/30"
            }`}
            title="Edytuj strefę awarii komórkowej GSM (Blackout)"
          >
            <Radio className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Strefa GSM</span>
          </button>

          <div className="w-px h-4 bg-border/60 mx-0.5" />

          {/* Fit View Button */}
          <Button
            size="xs"
            variant="ghost"
            onClick={fitToBoundary}
            className="h-7 px-2 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-950/40 text-xs gap-1"
            title="Wyśrodkuj widok na strefie"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Dopasuj</span>
          </Button>
        </div>
      </div>

      {/* 2. LEAFLET MAP CANVAS */}
      <div ref={mapContainerRef} className="w-full flex-1 min-h-[380px] z-10" />

      {/* 3. SUBTLE BOTTOM-RIGHT DIMENSION BADGE (Clean, minimal, non-intrusive) */}
      <div className="absolute bottom-3 right-3 z-20 pointer-events-auto">
        <div className="flex items-center gap-2 bg-card/90 backdrop-blur-md border border-border/80 px-3 py-1.5 rounded-lg shadow-lg text-xs font-mono">
          <span className="text-muted-foreground">Strefa:</span>
          <span className="font-bold text-cyan-400">
            {(areaW / 1000).toFixed(1)} × {(areaH / 1000).toFixed(1)} km
          </span>
          <span className="text-border">|</span>
          <span className="font-semibold text-emerald-400">{totalAreaKm2} km²</span>
        </div>
      </div>

      {/* 4. FLOATING HINT BANNER */}
      {(interactionMode !== "view" || feedbackToast) && (
        <div className="absolute bottom-12 left-1/2 -translate-x-1/2 z-20 bg-background/95 backdrop-blur-md border border-cyan-500/60 px-4 py-2 rounded-full text-xs text-cyan-300 shadow-2xl flex items-center gap-2.5 pointer-events-auto animate-in fade-in slide-in-from-bottom-2">
          {feedbackToast ? (
            <span>{feedbackToast}</span>
          ) : (
            <>
              {interactionMode === "add_victim" && (
                <span className="flex items-center gap-1.5 text-rose-300">
                  <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                  Kliknij na mapie, aby postawić ofiarę ({victimSignalType === "WIFI_PROBE_REQ" ? "Wi-Fi" : "LTE"})
                </span>
              )}
              {interactionMode === "edit_gsm" && (
                <span className="flex items-center gap-1.5 text-rose-300">
                  <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                  Przeciągaj epicentrum 🔴 lub promień 🟠. Kliknij mapę, aby przenieść strefę awarii.
                </span>
              )}
              {interactionMode === "set_gcs" && "🏢 Kliknij na mapie, aby przestawić bazę masztu GCS"}
              {interactionMode === "set_center" && "📍 Kliknij na mapie, aby przenieść centrum strefy"}
            </>
          )}

          {interactionMode !== "view" && (
            <button
              onClick={() => setInteractionMode("view")}
              className="ml-2 px-2 py-0.5 rounded bg-muted/60 hover:bg-muted text-[11px] text-muted-foreground hover:text-foreground font-mono"
            >
              Gotowe [Esc]
            </button>
          )}
        </div>
      )}
    </div>
  );
}
