"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import {
  Sliders,
  Plane,
  Radio,
  MapPin,
  Share2,
  Users,
  Save,
  Rocket,
  Sparkles,
  Plus,
  Trash2,
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Settings,
  Shield,
  Clock,
  Compass,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

// Dynamically import SetupMapPreview to avoid SSR issues with Leaflet
const SetupMapPreview = dynamic(
  () => import("./SetupMapPreview").then((mod) => mod.SetupMapPreview),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[350px] flex items-center justify-center bg-[#090d16] border border-border/50 rounded-xl text-cyan-400 font-mono text-xs gap-2">
        <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span>Ładowanie mapy taktycznej GIS...</span>
      </div>
    ),
  }
);

// 4 Primary Tactical Presets (Simple & Intuitive)
const PRESETS = [
  {
    id: "tatry_zakopane",
    name: "Tatry / Zakopane",
    badge: "GÓRSKI SAR",
    icon: "🏔️",
    desc: "10×10 km • 4 UAV • Teren wysokogórski",
    config: {
      area: {
        origin_lat: 49.2992,
        origin_lon: 19.9395,
        area_width_m: 10000.0,
        area_height_m: 10000.0,
        gcs_offset_x_m: -1500.0,
        gcs_offset_y_m: -1500.0,
      },
      swarm: {
        num_drones: 4,
        cruise_speed_mps: 18.0,
        search_altitude_m: 80.0,
        lane_spacing_m: 180.0,
        planner_mode: "RELAY_ANCHORED",
        battery_low_threshold: 25.0,
        callsigns: ["Eagle-1", "Eagle-2", "Eagle-3", "Eagle-4"],
      },
      mesh: {
        mesh_range_m: 3500.0,
        gcs_range_m: 7500.0,
        tx_power_dbm: 33.0,
        mesh_sensitivity_dbm: -100.0,
      },
      rf: {
        pl_0_dbm: 42.0,
        path_loss_exponent: 3.2,
        shadowing_sigma_db: 4.5,
        rx_sensitivity_dbm: -98.0,
      },
      gsm: {
        normal_rssi_dbm: -75.0,
        blackout_rssi_dbm: -122.0,
        tower_offset_m: 2800.0,
        grid_resolution_m: 200.0,
      },
      victims: [
        { mac: "e2:11:45:90:bc:31", local_x: 2200.0, local_y: 1800.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 23.0, burst_interval_sec: 4.0 },
        { mac: "bc:88:21:40:99:12", local_x: -2400.0, local_y: 2100.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 16.0, burst_interval_sec: 6.0 },
        { mac: "32:fe:09:aa:51:77", local_x: 1600.0, local_y: -2500.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 21.0, burst_interval_sec: 5.5 },
      ],
    },
  },
  {
    id: "krakow_blackout",
    name: "Kraków Urban",
    badge: "MIEJSKI",
    icon: "🏙️",
    desc: "4×4 km • 6 UAV • Gęsty Mesh",
    config: {
      area: {
        origin_lat: 50.0614,
        origin_lon: 19.9366,
        area_width_m: 4000.0,
        area_height_m: 4000.0,
        gcs_offset_x_m: -650.0,
        gcs_offset_y_m: -650.0,
      },
      swarm: {
        num_drones: 6,
        cruise_speed_mps: 15.0,
        search_altitude_m: 60.0,
        lane_spacing_m: 120.0,
        planner_mode: "SYNCHRONIZED_FRONT",
        battery_low_threshold: 20.0,
        callsigns: ["Vulture-1", "Vulture-2", "Vulture-3", "Vulture-4", "Vulture-5", "Vulture-6"],
      },
      mesh: {
        mesh_range_m: 2500.0,
        gcs_range_m: 5000.0,
        tx_power_dbm: 30.0,
        mesh_sensitivity_dbm: -97.0,
      },
      rf: {
        pl_0_dbm: 40.0,
        path_loss_exponent: 2.8,
        shadowing_sigma_db: 3.0,
        rx_sensitivity_dbm: -96.0,
      },
      gsm: {
        normal_rssi_dbm: -65.0,
        blackout_rssi_dbm: -118.0,
        tower_offset_m: 1800.0,
        grid_resolution_m: 140.0,
      },
      victims: [
        { mac: "d8:3a:dd:44:91:a1", local_x: 180.0, local_y: 120.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 17.0, burst_interval_sec: 4.5 },
        { mac: "a4:c3:61:92:ef:22", local_x: -650.0, local_y: 420.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 15.0, burst_interval_sec: 6.0 },
        { mac: "7c:50:79:33:14:bb", local_x: 850.0, local_y: 680.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 22.0, burst_interval_sec: 5.0 },
        { mac: "f0:99:bf:10:8c:6e", local_x: -320.0, local_y: -580.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 16.0, burst_interval_sec: 7.0 },
      ],
    },
  },
  {
    id: "bieszczady_sar",
    name: "Bieszczady Wilderness",
    badge: "LEŚNY SAR",
    icon: "🌲",
    desc: "6×6 km • 4 UAV • Daleki zasięg C2",
    config: {
      area: {
        origin_lat: 49.1245,
        origin_lon: 22.6512,
        area_width_m: 6000.0,
        area_height_m: 6000.0,
        gcs_offset_x_m: -1200.0,
        gcs_offset_y_m: -1200.0,
      },
      swarm: {
        num_drones: 4,
        cruise_speed_mps: 18.0,
        search_altitude_m: 80.0,
        lane_spacing_m: 200.0,
        planner_mode: "RELAY_ANCHORED",
        battery_low_threshold: 25.0,
        callsigns: ["Eagle-1", "Eagle-2", "Eagle-3", "Eagle-4"],
      },
      mesh: {
        mesh_range_m: 3500.0,
        gcs_range_m: 7500.0,
        tx_power_dbm: 33.0,
        mesh_sensitivity_dbm: -100.0,
      },
      rf: {
        pl_0_dbm: 42.0,
        path_loss_exponent: 3.2,
        shadowing_sigma_db: 4.5,
        rx_sensitivity_dbm: -98.0,
      },
      gsm: {
        normal_rssi_dbm: -75.0,
        blackout_rssi_dbm: -122.0,
        tower_offset_m: 2800.0,
        grid_resolution_m: 200.0,
      },
      victims: [
        { mac: "e2:11:45:90:bc:31", local_x: 1200.0, local_y: 800.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 23.0, burst_interval_sec: 4.0 },
        { mac: "bc:88:21:40:99:12", local_x: -1400.0, local_y: 1100.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 16.0, burst_interval_sec: 6.0 },
        { mac: "32:fe:09:aa:51:77", local_x: 600.0, local_y: -1500.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 21.0, burst_interval_sec: 5.5 },
      ],
    },
  },
  {
    id: "fast_sweep",
    name: "Fast Grid Sweep",
    badge: "SZYBKI FRONT",
    icon: "⚡",
    desc: "3.5×3.5 km • 8 UAV • 20 m/s",
    config: {
      area: {
        origin_lat: 50.0614,
        origin_lon: 19.9366,
        area_width_m: 3500.0,
        area_height_m: 3500.0,
        gcs_offset_x_m: -500.0,
        gcs_offset_y_m: -500.0,
      },
      swarm: {
        num_drones: 8,
        cruise_speed_mps: 20.0,
        search_altitude_m: 50.0,
        lane_spacing_m: 90.0,
        planner_mode: "SYNCHRONIZED_FRONT",
        battery_low_threshold: 20.0,
        callsigns: ["Falcon-1", "Falcon-2", "Falcon-3", "Falcon-4", "Falcon-5", "Falcon-6", "Falcon-7", "Falcon-8"],
      },
      mesh: {
        mesh_range_m: 2000.0,
        gcs_range_m: 4500.0,
        tx_power_dbm: 30.0,
        mesh_sensitivity_dbm: -97.0,
      },
      rf: {
        pl_0_dbm: 40.0,
        path_loss_exponent: 2.8,
        shadowing_sigma_db: 3.0,
        rx_sensitivity_dbm: -96.0,
      },
      gsm: {
        normal_rssi_dbm: -65.0,
        blackout_rssi_dbm: -118.0,
        tower_offset_m: 1600.0,
        grid_resolution_m: 120.0,
      },
      victims: [
        { mac: "11:22:33:44:55:66", local_x: 200.0, local_y: 200.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 17.0, burst_interval_sec: 3.0 },
        { mac: "77:88:99:aa:bb:cc", local_x: -400.0, local_y: -300.0, signal_type: "LTE_DIRECT_UPLINK", tx_power_dbm: 20.0, burst_interval_sec: 4.0 },
        { mac: "dd:ee:ff:00:11:22", local_x: 600.0, local_y: -400.0, signal_type: "WIFI_PROBE_REQ", tx_power_dbm: 16.0, burst_interval_sec: 5.0 },
      ],
    },
  },
];

export function SimulationStudio({
  initialConfig,
  onSaveConfig,
  onLaunchOperator,
  onChangeConfig,
}) {
  const [formConfig, setFormConfig] = useState(() => initialConfig || PRESETS[0].config);
  const [selectedPreset, setSelectedPreset] = useState("tatry_zakopane");
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const initialConfigAppliedRef = useRef(false);

  // Sync with initialConfig once when loaded from backend without infinite loop
  useEffect(() => {
    if (initialConfig && Object.keys(initialConfig).length > 0 && !initialConfigAppliedRef.current) {
      setFormConfig(initialConfig);
      initialConfigAppliedRef.current = true;
    }
  }, [initialConfig]);

  // Sync state upward to parent so operator mode always knows the selected area
  useEffect(() => {
    if (formConfig && onChangeConfig) {
      onChangeConfig(formConfig);
    }
  }, [formConfig, onChangeConfig]);

  if (!formConfig) return null;

  // Preset Selection Handler
  const applyPreset = (presetId) => {
    const p = PRESETS.find((item) => item.id === presetId);
    if (!p) return;
    setSelectedPreset(presetId);
    setFormConfig(JSON.parse(JSON.stringify(p.config)));
    setSaveStatus("Zastosowano: " + p.name);
    setTimeout(() => setSaveStatus(null), 2500);
  };

  // Helper field updater
  const updateField = (section, field, value) => {
    setFormConfig((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value,
      },
    }));
  };

  // Set square dimension for area
  const setAreaDimensionKm = (km) => {
    const meters = Math.max(1000, Math.min(25000, Math.round(km * 1000)));
    setFormConfig((prev) => ({
      ...prev,
      area: {
        ...prev.area,
        area_width_m: meters,
        area_height_m: meters,
      },
    }));
  };

  // Set number of drones
  const setDronesCount = (count) => {
    setFormConfig((prev) => {
      const callsigns = Array.from({ length: count }, (_, i) => `Drone-${i + 1}`);
      return {
        ...prev,
        swarm: {
          ...prev.swarm,
          num_drones: count,
          callsigns,
        },
      };
    });
  };

  // Victim helpers
  const addVictim = () => {
    const randMac = `02:00:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(
      Math.random() * 89 + 10
    )}:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(Math.random() * 89 + 10)}`;
    const newVictim = {
      mac: randMac,
      local_x: Math.round((Math.random() * (areaW * 0.6) - areaW * 0.3)),
      local_y: Math.round((Math.random() * (areaH * 0.6) - areaH * 0.3)),
      signal_type: "WIFI_PROBE_REQ",
      tx_power_dbm: 16.0,
      burst_interval_sec: 5.0,
    };
    setFormConfig((prev) => ({
      ...prev,
      victims: [...(prev.victims || []), newVictim],
    }));
    setSaveStatus("Dodano nową ofiarę.");
    setTimeout(() => setSaveStatus(null), 2000);
  };

  const removeVictim = (index) => {
    setFormConfig((prev) => ({
      ...prev,
      victims: prev.victims.filter((_, idx) => idx !== index),
    }));
    setSaveStatus("Usunięto ofiarę.");
    setTimeout(() => setSaveStatus(null), 2000);
  };

  // Save handler
  const handleSaveOnly = async () => {
    setIsSaving(true);
    try {
      if (onSaveConfig) {
        await onSaveConfig(formConfig);
        setSaveStatus("Zapisano pomyślnie!");
        setTimeout(() => setSaveStatus(null), 3000);
      }
    } catch (e) {
      console.error(e);
      setSaveStatus("Błąd zapisu.");
    } finally {
      setIsSaving(false);
    }
  };

  // Launch Operator handler
  const handleDeployAndLaunch = async () => {
    setIsSaving(true);
    try {
      if (onSaveConfig) {
        await onSaveConfig(formConfig);
      }
      if (onLaunchOperator) {
        onLaunchOperator(formConfig);
      }
    } catch (e) {
      console.error(e);
      setSaveStatus("Błąd uruchamiania.");
      setIsSaving(false);
    }
  };

  // Metrics
  const areaW = parseFloat(formConfig.area?.area_width_m) || 4000;
  const areaH = parseFloat(formConfig.area?.area_height_m) || 4000;
  const areaKm = (Math.max(areaW, areaH) / 1000).toFixed(1);
  const totalAreaKm2 = ((areaW * areaH) / 1e6).toFixed(1);
  const numUav = parseInt(formConfig.swarm?.num_drones) || 4;
  const speed = parseFloat(formConfig.swarm?.cruise_speed_mps) || 15;
  const laneSpacing = parseFloat(formConfig.swarm?.lane_spacing_m) || 120;
  const victimsCount = formConfig.victims?.length || 0;
  const sweepTimeMin = Math.max(5, Math.round((areaW * areaH) / (numUav * speed * laneSpacing * 60)));

  // GSM Metrics & Helpers
  const defaultGsmRadius = Math.max(areaW, areaH) * 0.65;
  const gsmRadius =
    parseFloat(formConfig.gsm?.blackout_radius_m) > 0
      ? parseFloat(formConfig.gsm?.blackout_radius_m)
      : defaultGsmRadius;
  const gsmRadiusKm = (gsmRadius / 1000).toFixed(1);
  const gsmAreaKm2 = ((Math.PI * gsmRadius * gsmRadius) / 1e6).toFixed(1);
  const towerDistM = parseFloat(formConfig.gsm?.tower_offset_m) || 1800;
  const towerDistKm = (towerDistM / 1000).toFixed(1);

  const applyGsmPreset = (type) => {
    if (type === "TOTAL") {
      const radius = Math.round(Math.max(areaW, areaH) * 0.85);
      setFormConfig((prev) => ({
        ...prev,
        gsm: {
          ...prev.gsm,
          blackout_radius_m: radius,
          blackout_rssi_dbm: -125.0,
          center_offset_x_m: 0,
          center_offset_y_m: 0,
        },
      }));
      setSaveStatus("Tryb GSM: Totalny Blackout 100%");
    } else if (type === "GRADIENT") {
      const radius = Math.round(Math.max(areaW, areaH) * 0.55);
      setFormConfig((prev) => ({
        ...prev,
        gsm: {
          ...prev.gsm,
          blackout_radius_m: radius,
          blackout_rssi_dbm: -115.0,
        },
      }));
      setSaveStatus("Tryb GSM: Zanikanie gradientowe");
    } else if (type === "LOCAL") {
      setFormConfig((prev) => ({
        ...prev,
        gsm: {
          ...prev.gsm,
          blackout_radius_m: 1500,
          blackout_rssi_dbm: -110.0,
        },
      }));
      setSaveStatus("Tryb GSM: Lokalna awaria masztu (1.5 km)");
    }
    setTimeout(() => setSaveStatus(null), 2500);
  };

  return (
    <div className="h-full min-h-0 flex flex-col p-3 md:p-3.5 overflow-hidden bg-[#070a10] text-foreground select-none font-sans">
      {/* 1. MINIMAL TOP BAR */}
      <div className="flex items-center justify-between gap-3 mb-2.5 shrink-0 border-b border-border/40 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-950/70 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
            <Sliders className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight text-foreground">
                Planowanie Misji SAR
              </h2>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Krok 1: Konfiguracja
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Wybierz scenariusz lub dostosuj obszar na mapie i uruchom rój dronów.
            </p>
          </div>
        </div>

        {/* Status message */}
        {saveStatus && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/50 text-emerald-400 text-xs animate-in fade-in">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {saveStatus}
          </div>
        )}
      </div>

      {/* 2. MAIN 2-COLUMN VIEW: CLEAN DOCKED SIDEBAR (Left ~380px) + HERO MAP WORKSPACE (Right) */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-3 overflow-hidden">
        {/* LEFT DOCKED CONTROLLER (Width: 4/12 on large screens, scrollable) */}
        <div className="lg:col-span-4 xl:col-span-4 h-full min-h-0 flex flex-col gap-2.5 overflow-hidden bg-card/60 border border-border/60 rounded-xl p-3 backdrop-blur-md shadow-xl">
          <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-3 pr-0.5">
            {/* SECTION 1: SCENARIUSZE (PRESETS) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> 1. Scenariusz Misji
                </span>
                <span className="text-[11px] text-muted-foreground">Szybki start</span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {PRESETS.map((p) => {
                  const isSelected = selectedPreset === p.id;
                  return (
                    <button
                      key={p.id}
                      onClick={() => applyPreset(p.id)}
                      className={`p-2.5 rounded-xl border text-left transition-all relative flex flex-col justify-between cursor-pointer ${
                        isSelected
                          ? "border-cyan-400 bg-cyan-950/40 text-cyan-100 shadow-[0_0_15px_rgba(0,240,255,0.2)] ring-1 ring-cyan-400"
                          : "border-border/60 bg-background/50 text-muted-foreground hover:border-border hover:text-foreground"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-lg leading-none">{p.icon}</span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                            isSelected
                              ? "bg-cyan-500/25 text-cyan-300 font-semibold"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {p.badge}
                        </span>
                      </div>
                      <div className="text-xs font-bold text-foreground truncate">
                        {p.name}
                      </div>
                      <div className="text-[10.5px] text-muted-foreground truncate mt-0.5">
                        {p.desc}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <Separator />

            {/* SECTION 2: OBSZAR POSZUKIWAŃ */}
            <div className="space-y-2 bg-background/50 border border-border/60 p-3 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-cyan-400" /> 2. Obszar Poszukiwań:
                </span>
                <div className="text-right">
                  <span className="text-base font-bold text-cyan-400 font-mono">
                    {areaKm} × {areaKm} km
                  </span>
                  <span className="text-xs text-muted-foreground ml-1.5 font-mono">({totalAreaKm2} km²)</span>
                </div>
              </div>

              <input
                type="range"
                min="2"
                max="20"
                step="0.5"
                value={parseFloat(areaKm)}
                onChange={(e) => setAreaDimensionKm(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 h-2 bg-muted/70 rounded-lg cursor-pointer"
              />

              <div className="flex items-center justify-between text-[10.5px] text-muted-foreground">
                <span>2 km (mały)</span>
                <span>10 km (standard)</span>
                <span>20 km (rozległy)</span>
              </div>
            </div>

            {/* SECTION 3: FLOTA DRONÓW */}
            <div className="space-y-2 bg-background/50 border border-border/60 p-3 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Plane className="w-3.5 h-3.5 text-emerald-400" /> 3. Flota Roju Dronów:
                </span>
                <span className="text-sm font-bold text-emerald-400 font-mono">{numUav} UAV</span>
              </div>

              <div className="grid grid-cols-4 gap-1.5">
                {[2, 4, 6, 8].map((count) => (
                  <button
                    key={count}
                    onClick={() => setDronesCount(count)}
                    className={`py-1.5 rounded-lg border text-center text-xs font-bold transition-all cursor-pointer ${
                      numUav === count
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/60 shadow-sm"
                        : "bg-background/80 text-muted-foreground border-border/50 hover:text-foreground hover:bg-muted/30"
                    }`}
                  >
                    {count} UAV
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground pt-1.5 border-t border-border/30">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-amber-400" /> Szacowany czas skanowania:
                </span>
                <span className="font-bold text-amber-400 font-mono">~{sweepTimeMin} min</span>
              </div>
            </div>

            {/* SECTION 4: AWARIA INFRASTRUKTURY GSM (BLACKOUT) */}
            <div className="space-y-2.5 bg-background/50 border border-rose-500/30 p-3 rounded-xl shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-rose-400" /> 4. Strefa Awarii GSM (Blackout):
                </span>
                <Badge variant="outline" className="text-[10px] font-mono text-rose-400 border-rose-500/40 bg-rose-950/30">
                  BRAK SIECI
                </Badge>
              </div>

              {/* Status info tiles */}
              <div className="grid grid-cols-2 gap-1.5 text-[11px] font-mono">
                <div className="bg-card/70 border border-border/50 rounded-lg p-2">
                  <span className="text-muted-foreground block text-[10px]">Promień awarii:</span>
                  <span className="text-rose-400 font-bold">{gsmRadiusKm} km</span>
                  <span className="text-muted-foreground text-[10px] ml-1">({gsmAreaKm2} km²)</span>
                </div>
                <div className="bg-card/70 border border-border/50 rounded-lg p-2">
                  <span className="text-muted-foreground block text-[10px]">Tłumienie w centrum:</span>
                  <span className="text-rose-400 font-bold">{formConfig.gsm?.blackout_rssi_dbm ?? -118} dBm</span>
                  <span className="text-muted-foreground text-[10px] ml-1">(Brak sieci)</span>
                </div>
              </div>

              {/* Slider: Promień Awarii */}
              <div>
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="text-muted-foreground">Promień zniszczeń / braku zasięgu:</span>
                  <span className="font-bold text-rose-400 font-mono">{gsmRadiusKm} km</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="15"
                  step="0.2"
                  value={parseFloat(gsmRadiusKm)}
                  onChange={(e) => updateField("gsm", "blackout_radius_m", Math.round(parseFloat(e.target.value) * 1000))}
                  className="w-full accent-rose-500 h-2 bg-muted/70 rounded-lg cursor-pointer"
                />
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>0.5 km (punktowy)</span>
                  <span>5 km (rejonowy)</span>
                  <span>15 km (katastrofalny)</span>
                </div>
              </div>

              {/* Quick Blackout Profiles */}
              <div className="grid grid-cols-3 gap-1 pt-1">
                <button
                  type="button"
                  onClick={() => applyGsmPreset("TOTAL")}
                  className="px-1.5 py-1 text-[10px] rounded bg-rose-950/40 hover:bg-rose-900/50 text-rose-300 border border-rose-500/40 font-medium transition-colors cursor-pointer"
                >
                  💥 100% Blackout
                </button>
                <button
                  type="button"
                  onClick={() => applyGsmPreset("GRADIENT")}
                  className="px-1.5 py-1 text-[10px] rounded bg-amber-950/40 hover:bg-amber-900/50 text-amber-300 border border-amber-500/40 font-medium transition-colors cursor-pointer"
                >
                  ⚡ Zanik Częściowy
                </button>
                <button
                  type="button"
                  onClick={() => applyGsmPreset("LOCAL")}
                  className="px-1.5 py-1 text-[10px] rounded bg-blue-950/40 hover:bg-blue-900/50 text-blue-300 border border-blue-500/40 font-medium transition-colors cursor-pointer"
                >
                  🎯 Awaria 1.5 km
                </button>
              </div>

              {/* Directional Shift / Placement Grid */}
              <div className="pt-1.5 border-t border-border/30 space-y-1.5">
                <div className="flex items-center justify-between text-[10.5px]">
                  <span className="text-muted-foreground">Pozycja epicentrum:</span>
                  <span className="font-mono text-rose-400 font-semibold">
                    ({Math.round(formConfig.gsm?.center_offset_x_m || 0)}m, {Math.round(formConfig.gsm?.center_offset_y_m || 0)}m)
                  </span>
                </div>
                <div className="grid grid-cols-5 gap-1">
                  <button
                    type="button"
                    title="Przesuń na Północny-Zachód"
                    onClick={() => {
                      const shift = Math.round(areaW * 0.25);
                      setFormConfig((prev) => ({
                        ...prev,
                        gsm: { ...prev.gsm, center_offset_x_m: -shift, center_offset_y_m: shift }
                      }));
                      setSaveStatus("Przesunięto awarię: Północny-Zachód");
                    }}
                    className="py-1 text-[10px] rounded bg-muted/60 hover:bg-muted text-foreground border border-border/50 font-mono transition-colors cursor-pointer"
                  >
                    ↖ Pn-Z
                  </button>
                  <button
                    type="button"
                    title="Przesuń na Północny-Wschód"
                    onClick={() => {
                      const shift = Math.round(areaW * 0.25);
                      setFormConfig((prev) => ({
                        ...prev,
                        gsm: { ...prev.gsm, center_offset_x_m: shift, center_offset_y_m: shift }
                      }));
                      setSaveStatus("Przesunięto awarię: Północny-Wschód");
                    }}
                    className="py-1 text-[10px] rounded bg-muted/60 hover:bg-muted text-foreground border border-border/50 font-mono transition-colors cursor-pointer"
                  >
                    ↗ Pn-W
                  </button>
                  <button
                    type="button"
                    title="Wycentruj w strefie"
                    onClick={() => {
                      setFormConfig((prev) => ({
                        ...prev,
                        gsm: { ...prev.gsm, center_offset_x_m: 0, center_offset_y_m: 0 }
                      }));
                      setSaveStatus("Wycentrowano awarię GSM");
                    }}
                    className="py-1 text-[10px] rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 font-bold transition-colors cursor-pointer"
                  >
                    🎯 Środek
                  </button>
                  <button
                    type="button"
                    title="Przesuń na Południowy-Zachód"
                    onClick={() => {
                      const shift = Math.round(areaW * 0.25);
                      setFormConfig((prev) => ({
                        ...prev,
                        gsm: { ...prev.gsm, center_offset_x_m: -shift, center_offset_y_m: -shift }
                      }));
                      setSaveStatus("Przesunięto awarię: Południowy-Zachód");
                    }}
                    className="py-1 text-[10px] rounded bg-muted/60 hover:bg-muted text-foreground border border-border/50 font-mono transition-colors cursor-pointer"
                  >
                    ↙ Pd-Z
                  </button>
                  <button
                    type="button"
                    title="Przesuń na Południowy-Wschód"
                    onClick={() => {
                      const shift = Math.round(areaW * 0.25);
                      setFormConfig((prev) => ({
                        ...prev,
                        gsm: { ...prev.gsm, center_offset_x_m: shift, center_offset_y_m: -shift }
                      }));
                      setSaveStatus("Przesunięto awarię: Południowy-Wschód");
                    }}
                    className="py-1 text-[10px] rounded bg-muted/60 hover:bg-muted text-foreground border border-border/50 font-mono transition-colors cursor-pointer"
                  >
                    ↘ Pd-W
                  </button>
                </div>
              </div>
            </div>

            {/* SECTION 5: OFIARY */}
            <div className="flex items-center justify-between p-3 bg-background/50 border border-border/60 rounded-xl">
              <div>
                <span className="text-xs font-semibold text-foreground block">
                  5. Poszukiwane Osoby:
                </span>
                <span className="text-[11px] text-muted-foreground">Sygnały Wi-Fi oraz LTE</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-rose-400 font-mono px-2 py-0.5 rounded bg-rose-950/40 border border-rose-500/40">
                  {victimsCount} celów
                </span>
                <Button
                  size="sm"
                  onClick={addVictim}
                  className="h-7 px-2.5 text-xs bg-rose-600 hover:bg-rose-500 text-white gap-1 cursor-pointer"
                >
                  <Plus className="w-3 h-3" /> + Dodaj
                </Button>
              </div>
            </div>

            <Separator />

            {/* SECTION 5: COLLAPSIBLE ADVANCED SETTINGS (DOMYŚLNIE ZWINIĘTE!) */}
            <div className="border border-border/60 rounded-xl overflow-hidden bg-background/30">
              <button
                onClick={() => setShowAdvanced((prev) => !prev)}
                className="w-full flex items-center justify-between p-2.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-2">
                  <Settings className="w-3.5 h-3.5 text-cyan-400" />
                  Zaawansowane Parametry (Radio & Łączność)
                </span>
                {showAdvanced ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>

              {showAdvanced && (
                <div className="p-3 border-t border-border/50 bg-background/60 space-y-2.5 text-xs animate-in fade-in slide-in-from-top-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Prędkość (m/s)</Label>
                      <Input
                        type="number"
                        value={formConfig.swarm?.cruise_speed_mps ?? 15}
                        onChange={(e) => updateField("swarm", "cruise_speed_mps", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Wysokość lotu (m)</Label>
                      <Input
                        type="number"
                        value={formConfig.swarm?.search_altitude_m ?? 80}
                        onChange={(e) => updateField("swarm", "search_altitude_m", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Zasięg Mesh P2P (m)</Label>
                      <Input
                        type="number"
                        value={formConfig.mesh?.mesh_range_m ?? 3500}
                        onChange={(e) => updateField("mesh", "mesh_range_m", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Zasięg Masztu GCS (m)</Label>
                      <Input
                        type="number"
                        value={formConfig.mesh?.gcs_range_m ?? 7500}
                        onChange={(e) => updateField("mesh", "gcs_range_m", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/40">
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Blackout RSSI (dBm)</Label>
                      <Input
                        type="number"
                        value={formConfig.gsm?.blackout_rssi_dbm ?? -118}
                        onChange={(e) => updateField("gsm", "blackout_rssi_dbm", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px] text-muted-foreground block mb-1">Zasięg Normalny BTS (dBm)</Label>
                      <Input
                        type="number"
                        value={formConfig.gsm?.normal_rssi_dbm ?? -65}
                        onChange={(e) => updateField("gsm", "normal_rssi_dbm", parseFloat(e.target.value))}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                  </div>

                  {/* Victims quick list */}
                  {formConfig.victims && formConfig.victims.length > 0 && (
                    <div className="pt-2 border-t border-border/40">
                      <Label className="text-[10px] text-muted-foreground block mb-1">
                        Lista Ofiar ({formConfig.victims.length}):
                      </Label>
                      <div className="space-y-1 max-h-24 overflow-y-auto custom-scrollbar">
                        {formConfig.victims.map((v, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-1.5 rounded-lg bg-background/80 border border-border/40 text-[11px]"
                          >
                            <span className="font-semibold text-rose-400 font-mono">
                              #{idx + 1} {v.signal_type === "WIFI_PROBE_REQ" ? "Wi-Fi" : "LTE"} ({Math.round(v.local_x)}m, {Math.round(v.local_y)}m)
                            </span>
                            <button
                              onClick={() => removeVictim(idx)}
                              className="text-rose-400 hover:text-rose-300 p-0.5"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* DOCKED BOTTOM ACTIONS */}
          <div className="shrink-0 pt-2 border-t border-border/50 flex flex-col gap-1.5">
            <Button
              size="default"
              disabled={isSaving}
              onClick={handleDeployAndLaunch}
              className="w-full h-11 font-sans text-xs font-bold tracking-wide uppercase gap-2 bg-gradient-to-r from-cyan-600 via-teal-600 to-emerald-600 hover:from-cyan-500 hover:to-emerald-500 text-white shadow-[0_0_20px_rgba(0,240,255,0.35)] transition-all cursor-pointer"
            >
              <Rocket className="w-4 h-4 fill-current" />
              ROZPOCZNIJ POSZUKIWANIA (PANEL OPERATORA) ➔
            </Button>

            <button
              onClick={handleSaveOnly}
              disabled={isSaving}
              className="text-[11px] text-center text-muted-foreground hover:text-cyan-300 transition-colors py-0.5 flex items-center justify-center gap-1 cursor-pointer"
            >
              <Save className="w-3 h-3" />
              Tylko zapisz konfigurację bez uruchamiania
            </button>
          </div>
        </div>

        {/* RIGHT HERO MAP WORKSPACE (Width: 8/12 on large screens, expansive and clear) */}
        <div className="lg:col-span-8 xl:col-span-8 h-full min-h-0 flex flex-col rounded-xl overflow-hidden border border-border/60 bg-[#090d16] shadow-2xl relative">
          <SetupMapPreview
            config={formConfig}
            onUpdateArea={(areaUpdates) => {
              setFormConfig((prev) => ({
                ...prev,
                area: {
                  ...prev.area,
                  ...areaUpdates,
                },
              }));
            }}
            onUpdateGsm={(gsmUpdates) => {
              setFormConfig((prev) => ({
                ...prev,
                gsm: {
                  ...(prev.gsm || {}),
                  ...gsmUpdates,
                },
              }));
            }}
            onAddVictim={(newVictim) => {
              setFormConfig((prev) => ({
                ...prev,
                victims: [...(prev.victims || []), newVictim],
              }));
              setSaveStatus("Dodano cel na mapie.");
              setTimeout(() => setSaveStatus(null), 2000);
            }}
            onUpdateVictim={(index, updatedFields) => {
              setFormConfig((prev) => {
                const updated = [...(prev.victims || [])];
                updated[index] = { ...updated[index], ...updatedFields };
                return { ...prev, victims: updated };
              });
            }}
            onRemoveVictim={(index) => {
              setFormConfig((prev) => ({
                ...prev,
                victims: prev.victims.filter((_, idx) => idx !== index),
              }));
              setSaveStatus("Usunięto cel.");
              setTimeout(() => setSaveStatus(null), 2000);
            }}
          />
        </div>
      </div>
    </div>
  );
}
