"use client";

import React from "react";
import { Sliders, MapPin, Plane, Share2, Radio, Users, Settings2, Play, Pause } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function SimulationContextBar({
  config,
  snapshot,
  onOpenSetup,
}) {
  const area = config?.area || {};
  const swarm = config?.swarm || {};
  const mesh = config?.mesh || {};
  const victims = config?.victims || [];

  const areaW = ((parseFloat(area.area_width_m) || 4000) / 1000).toFixed(1);
  const areaH = ((parseFloat(area.area_height_m) || 4000) / 1000).toFixed(1);
  const numDrones = swarm.num_drones || snapshot?.drones?.length || 6;
  const p2pRangeKm = ((parseFloat(mesh.mesh_range_m) || 2500) / 1000).toFixed(1);
  const gcsRangeKm = ((parseFloat(mesh.gcs_range_m) || 5000) / 1000).toFixed(1);
  const victimsCount = victims.length || snapshot?.pois?.length || 0;

  const missionState = snapshot?.mission_state || "IDLE";
  const isRunning = missionState === "RUNNING";
  const isPaused = missionState === "PAUSED";

  return (
    <div className="h-8 shrink-0 px-3.5 flex items-center justify-between gap-3 bg-muted/20 border-b border-border/40 text-xs font-sans text-muted-foreground select-none whitespace-nowrap overflow-x-auto custom-scrollbar">
      {/* Contextual telemetry badges */}
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 font-semibold text-foreground">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          Aktywny Scenariusz:
        </span>

        <span className="flex items-center gap-1 text-cyan-300 font-mono">
          <MapPin className="w-3.5 h-3.5 text-cyan-400" />
          {areaW} × {areaH} km
        </span>

        <span className="text-border">|</span>

        <span className="flex items-center gap-1 text-emerald-300 font-mono">
          <Plane className="w-3.5 h-3.5 text-emerald-400" />
          {numDrones} UAV
        </span>

        <span className="text-border">|</span>

        <span className="flex items-center gap-1 text-rose-300 font-mono">
          <Users className="w-3.5 h-3.5 text-rose-400" />
          {victimsCount} celów
        </span>

        <span className="text-border hidden sm:inline">|</span>

        <span className="flex items-center gap-1 text-amber-300 font-mono hidden sm:flex">
          <Radio className="w-3.5 h-3.5 text-amber-400" />
          C2 {gcsRangeKm} km
        </span>

        {snapshot?.stats?.gsm_sectors_total > 0 && (
          <>
            <span className="text-border hidden md:inline">|</span>
            <span className="flex items-center gap-1 font-mono hidden md:flex">
              <span className={`w-2 h-2 rounded-full ${snapshot.stats.gsm_sectors_blackout > 0 ? "bg-rose-500 animate-pulse" : "bg-cyan-400"}`} />
              <span className="text-muted-foreground">GSM:</span>
              <span className="text-cyan-300">
                {snapshot.stats.gsm_sectors_surveyed}/{snapshot.stats.gsm_sectors_total}
              </span>
              {snapshot.stats.gsm_sectors_blackout > 0 && (
                <span className="text-rose-400 font-bold ml-0.5">
                  ({snapshot.stats.gsm_sectors_blackout} ⚠️)
                </span>
              )}
            </span>
          </>
        )}
      </div>

      {/* Action: Return to Setup / Reconfigure */}
      <div className="flex items-center gap-2">
        <Button
          size="xs"
          variant="outline"
          onClick={onOpenSetup}
          className="h-6 px-2.5 text-[11px] font-sans font-medium border-cyan-500/40 bg-cyan-950/20 text-cyan-300 hover:bg-cyan-900/40 gap-1.5 cursor-pointer"
        >
          <Sliders className="w-3 h-3 text-cyan-400" />
          Dostosuj Parametry w Planowaniu
        </Button>
      </div>
    </div>
  );
}
