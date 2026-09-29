"use client";

import React from "react";
import { Play, Pause, RotateCcw, Plus, Settings2, Zap, Radio, Sliders, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function TopNav({
  mode = "setup",
  onModeChange,
  snapshot,
  connected,
  connecting,
  speedMultiplier,
  onStart,
  onPause,
  onResume,
  onReset,
  onSetSpeed,
  onOpenInject,
  onOpenConfig,
}) {
  const missionState = snapshot?.mission_state || "IDLE";
  const stats = snapshot?.stats;
  const mesh = snapshot?.mesh;

  const isRunning = missionState === "RUNNING";
  const isPaused = missionState === "PAUSED";
  const isIdle = missionState === "IDLE";

  return (
    <header className="h-12 md:h-13 shrink-0 border-b border-border/40 bg-card/85 backdrop-blur-md px-3.5 py-1.5 flex items-center justify-between gap-3 z-30 shadow-md select-none font-sans whitespace-nowrap overflow-x-auto custom-scrollbar">
      {/* 1. Brand & Connection Status */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-black tracking-widest text-cyan-400">OUTOFBLACK</span>
          <span className="text-muted-foreground text-xs font-normal">| Rój SAR</span>
        </div>

        <div className="flex items-center gap-1.5 pl-2 border-l border-border/40 text-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              connected
                ? "bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]"
                : connecting
                ? "bg-amber-400 animate-pulse"
                : "bg-rose-500"
            }`}
          />
          <span className="text-[11px] text-muted-foreground hidden sm:inline">
            {connected ? "Połączono" : connecting ? "Łączenie..." : "Offline"}
          </span>
        </div>
      </div>

      {/* 2. Tactical Workspace Mode Switcher (Setup vs. Operator) */}
      <div className="flex items-center bg-background/90 border border-border/70 rounded-xl p-0.5 shadow-inner shrink-0">
        <button
          onClick={() => onModeChange && onModeChange("setup")}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            mode === "setup"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm"
              : "text-muted-foreground hover:text-foreground border border-transparent"
          }`}
        >
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          <span>1. Planowanie Misji</span>
        </button>

        <button
          onClick={() => onModeChange && onModeChange("operator")}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            mode === "operator"
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 shadow-sm"
              : "text-muted-foreground hover:text-foreground border border-transparent"
          }`}
        >
          <Radio className="w-3.5 h-3.5 text-emerald-400" />
          <span>2. Panel Dowodzenia</span>
          {connected && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5" />}
        </button>
      </div>

      {/* 3. Primary Mission Controls & Quick Telemetry */}
      <div className="flex items-center gap-2.5 shrink-0">
        {mode === "operator" ? (
          <>
            {isIdle || isPaused ? (
              <Button
                size="sm"
                onClick={isPaused ? onResume : onStart}
                className="h-8 px-3 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold gap-1.5 shadow-[0_0_10px_rgba(16,185,129,0.3)] transition-all cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>{isPaused ? "Wznów Misję" : "Start Roju"}</span>
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={onPause}
                className="h-8 px-3 border-amber-500/50 hover:bg-amber-500/10 text-amber-400 text-xs font-semibold gap-1.5 cursor-pointer"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Wstrzymaj</span>
              </Button>
            )}

            <Button
              size="sm"
              variant="outline"
              onClick={onReset}
              className="h-8 px-2.5 border-border/60 hover:bg-muted text-xs text-muted-foreground hover:text-foreground gap-1 cursor-pointer"
              title="Zresetuj misję do pozycji startowej"
            >
              <RotateCcw className="w-3 h-3" />
              <span className="hidden sm:inline">Reset</span>
            </Button>

            <div className="h-4 w-px bg-border/40 mx-0.5 hidden lg:block" />

            {/* Speed Multiplier */}
            <div className="hidden lg:flex items-center bg-background/80 border border-border/60 rounded-lg p-0.5 gap-0.5">
              <span className="text-[10px] text-muted-foreground px-1.5 flex items-center gap-1 font-mono">
                <Zap className="w-3 h-3 text-cyan-400" />
                <span>PRĘDKOŚĆ:</span>
              </span>
              {[1.0, 2.0, 5.0].map((mult) => (
                <button
                  key={mult}
                  onClick={() => onSetSpeed(mult)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-colors cursor-pointer ${
                    speedMultiplier === mult
                      ? "bg-cyan-500/25 text-cyan-300 border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {mult}x
                </button>
              ))}
            </div>

            <div className="h-4 w-px bg-border/40 mx-0.5 hidden lg:block" />

            {/* Inject Victim Button */}
            <Button
              size="sm"
              variant="outline"
              onClick={onOpenInject}
              className="h-8 px-2.5 border-rose-500/40 bg-rose-950/20 text-rose-400 hover:bg-rose-900/30 text-xs font-medium gap-1 cursor-pointer"
            >
              <Plus className="w-3 h-3" />
              <span className="hidden sm:inline">+ Ofiara</span>
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            onClick={() => onModeChange && onModeChange("operator")}
            className="h-8 px-3.5 text-xs font-semibold gap-1.5 bg-gradient-to-r from-cyan-600 to-emerald-600 hover:from-cyan-500 hover:to-emerald-500 text-white shadow-sm cursor-pointer"
          >
            <span>Przejdź do Panelu Operacyjnego ➔</span>
          </Button>
        )}

        {/* Live Metrics Telemetry Badges */}
        {mode === "operator" && (
          <div className="flex items-center gap-2.5 pl-2.5 border-l border-border/40 text-xs">
            <div className="text-center">
              <div className="text-[10px] text-muted-foreground leading-none">Czas</div>
              <div className="font-bold text-foreground font-mono text-xs leading-tight mt-0.5">
                {stats?.elapsed_time_sec ? `${Math.round(stats.elapsed_time_sec)}s` : "0s"}
              </div>
            </div>

            <div className="border-l border-border/40 pl-2.5 text-center">
              <div className="text-[10px] text-muted-foreground leading-none">Pokrycie</div>
              <div className="font-bold text-cyan-400 font-mono text-xs leading-tight mt-0.5">
                {stats?.area_covered_pct ?? 0}%
              </div>
            </div>

            <div className="border-l border-border/40 pl-2.5 text-center">
              <div className="text-[10px] text-muted-foreground leading-none">Odnaleziono</div>
              <div className="font-bold text-rose-400 font-mono text-xs leading-tight mt-0.5">
                {stats?.pois_discovered ?? 0}
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
