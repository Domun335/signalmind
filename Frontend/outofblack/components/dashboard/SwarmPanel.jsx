"use client";

import React from "react";
import {
  Battery,
  BatteryCharging,
  BatteryWarning,
  Plane,
  ArrowRight,
  Radio,
  ShieldAlert,
  RotateCcw,
  Play,
  CheckCircle2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export function SwarmPanel({ snapshot, onFocusDrone, onSwapBattery, onRelaunchDrone }) {
  const drones = snapshot?.drones || [];
  const mesh = snapshot?.mesh;
  const routes = mesh?.routes_to_gcs || {};

  const hasSwappable = drones.some(
    (d) => d.status === "STANDBY" && d.battery_pct < 99.5
  );
  const hasReadyToRelaunch = drones.some(
    (d) => d.status === "STANDBY" && d.battery_pct >= 25.0
  );

  return (
    <Card className="h-full min-h-0 flex flex-col border-border/50 bg-card/50 backdrop-blur-md shadow-lg overflow-hidden">
      <CardHeader className="px-3 py-2 shrink-0 border-b border-border/40 bg-muted/20 flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Plane className="w-3.5 h-3.5 text-cyan-400" />
          <CardTitle className="text-xs font-mono font-bold tracking-wide uppercase text-foreground">
            Rój UAV ({drones.length})
          </CardTitle>
        </div>
        <div className="flex items-center gap-1.5">
          {hasSwappable && (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                onSwapBattery && onSwapBattery(null);
              }}
              className="h-5 px-1.5 text-[9px] font-mono border-amber-500/50 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 gap-1 cursor-pointer"
              title="Wymień baterie we wszystkich oczekujących dronach w bazie na 100%"
            >
              <BatteryCharging className="w-2.5 h-2.5 text-amber-400" />
              <span>Wymień baterie</span>
            </Button>
          )}
          {hasReadyToRelaunch && (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                onRelaunchDrone && onRelaunchDrone(null);
              }}
              className="h-5 px-1.5 text-[9px] font-mono border-emerald-500/50 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 gap-1 cursor-pointer"
              title="Wyślij wszystkie gotowe drony do misji"
            >
              <Play className="w-2.5 h-2.5 fill-current text-emerald-400" />
              <span>Start roju</span>
            </Button>
          )}
          {mesh?.gateway_id && (
            <Badge variant="outline" className="text-[9px] font-mono border-amber-500/40 bg-amber-950/20 text-amber-400 px-1 py-0 h-4">
              GW: {mesh.gateway_id}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-2 flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-2">
        {drones.length === 0 ? (
          <div className="h-28 flex items-center justify-center text-xs font-mono text-muted-foreground text-center">
            Oczekiwanie na telemetrię roju...
          </div>
        ) : (
          drones.map((d) => {
            const isGateway = d.is_gateway;
            const route = routes[d.id] ? routes[d.id].join(" ➔ ") : isGateway ? "BEZPOŚREDNI C2" : "POZA ZASIĘGIEM";
            const isLowBat = d.battery_pct <= 20;
            const isMedBat = d.battery_pct <= 50;

            const isReturning = d.status === "RETURNING";
            const isStandby = d.status === "STANDBY";
            const isHovering = d.status === "HOVERING";
            const isTransit = d.status === "TRANSIT";

            const isDepleted = isStandby && (d.needs_battery_swap || d.battery_pct < 30);
            const isReady = isStandby && (d.battery_pct >= 90 || d.battery_swapped);

            const batColor = isLowBat
              ? "text-rose-400"
              : isMedBat
              ? "text-amber-400"
              : "text-emerald-400";

            return (
              <div
                key={d.id}
                onClick={() => onFocusDrone && onFocusDrone({ lat: d.lat, lon: d.lon })}
                className={`p-2 rounded-lg border transition-all cursor-pointer select-none ${
                  isReturning
                    ? "border-amber-500/60 bg-amber-950/20 hover:border-amber-400/80 shadow-[0_0_12px_rgba(245,158,11,0.15)]"
                    : isStandby && isDepleted
                    ? "border-rose-500/50 bg-rose-950/15 hover:border-rose-400/70"
                    : isGateway
                    ? "border-amber-500/40 bg-amber-950/15 hover:border-amber-400/60 shadow-[0_0_12px_rgba(255,183,0,0.06)]"
                    : "border-border/60 bg-background/60 hover:border-cyan-500/40 hover:bg-cyan-950/10"
                }`}
              >
                {/* Header: ID, Callsign & Role / Status Badge */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-xs font-bold text-foreground">
                      {d.id} <span className="text-muted-foreground font-normal text-[11px]">{`// ${d.callsign}`}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {isReturning ? (
                      <Badge
                        variant="outline"
                        className="text-[8.5px] font-mono font-bold px-1.5 py-0 h-4 border-amber-500/60 bg-amber-950/40 text-amber-300 animate-pulse flex items-center gap-1"
                      >
                        <RotateCcw className="w-2.5 h-2.5 animate-spin" />
                        POWRÓT (RTL)
                      </Badge>
                    ) : isStandby ? (
                      <Badge
                        variant="outline"
                        className={`text-[8.5px] font-mono font-bold px-1 py-0 h-3.5 leading-none ${
                          isDepleted
                            ? "border-rose-500/60 bg-rose-950/40 text-rose-300 animate-pulse"
                            : isReady
                            ? "border-emerald-500/60 bg-emerald-950/40 text-emerald-300"
                            : "border-amber-500/50 bg-amber-950/30 text-amber-300"
                        }`}
                      >
                        {isDepleted
                          ? "BAZA: WYMAGA WYMIANY"
                          : isReady
                          ? "BAZA: GOTOWY (100%)"
                          : `BAZA: STANDBY (${Math.round(d.battery_pct)}%)`}
                      </Badge>
                    ) : isHovering ? (
                      <Badge
                        variant="outline"
                        className="text-[8.5px] font-mono font-bold px-1 py-0 h-3.5 leading-none border-purple-500/50 bg-purple-950/30 text-purple-300"
                      >
                        ZAWIS / POI
                      </Badge>
                    ) : isTransit ? (
                      <Badge
                        variant="outline"
                        className="text-[8.5px] font-mono font-bold px-1 py-0 h-3.5 leading-none border-cyan-500/50 bg-cyan-950/30 text-cyan-300"
                      >
                        {d.target_poi_id ? "DOLOT DO POI" : "POWRÓT NA TRASĘ"}
                      </Badge>
                    ) : (
                      <Badge
                        variant="outline"
                        className={`text-[8.5px] font-mono font-bold px-1 py-0 h-3.5 leading-none ${
                          isGateway
                            ? "border-amber-500/50 bg-amber-500/20 text-amber-300"
                            : "border-cyan-500/40 bg-cyan-950/30 text-cyan-400"
                        }`}
                      >
                        {isGateway ? "★ GATEWAY" : d.role}
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Battery bar & Status */}
                <div className="space-y-0.5 mb-1.5">
                  <div className="flex items-center justify-between text-[10px] font-mono leading-tight">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      {isLowBat ? (
                        <BatteryWarning className="w-2.5 h-2.5 text-rose-400 animate-pulse" />
                      ) : (
                        <Battery className="w-2.5 h-2.5 text-muted-foreground" />
                      )}
                      Bateria:
                    </span>
                    <div className="flex items-center gap-1.5">
                      {d.battery_drain_rate > 0 && !isStandby && (
                        <span
                          className="text-[9px] text-muted-foreground/80 font-mono"
                          title={`Aktualne tempo zużycia: -${(d.battery_drain_rate * 60).toFixed(1)}%/min (-${d.battery_drain_rate.toFixed(3)}%/s)`}
                        >
                          (-{(d.battery_drain_rate * 60).toFixed(1)}%/min)
                        </span>
                      )}
                      <span className={`font-bold ${batColor}`}>{Number(d.battery_pct).toFixed(1)}%</span>
                    </div>
                  </div>
                  <Progress
                    value={d.battery_pct}
                    className="h-1 bg-muted/60"
                    indicatorClassName={
                      isLowBat ? "bg-rose-500" : isMedBat ? "bg-amber-500" : "bg-emerald-500"
                    }
                  />
                </div>

                {/* Flight telemetry row */}
                <div className="grid grid-cols-3 gap-1 text-[9.5px] font-mono text-muted-foreground bg-muted/30 p-1 rounded">
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">PUŁAP</span>
                    <span className="font-semibold text-foreground">{d.alt_m}m</span>
                  </div>
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">PRĘDKOŚĆ</span>
                    <span className="font-semibold text-foreground">{d.speed_mps}m/s</span>
                  </div>
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">PAKIETY RF</span>
                    <span className="font-semibold text-cyan-400">{d.packets_sniffed}</span>
                  </div>
                </div>

                {/* Multi-Hop Mesh Route to GCS */}
                <div className="mt-1.5 pt-1 border-t border-border/40 flex items-center justify-between text-[9px] font-mono">
                  <span className="text-muted-foreground uppercase flex items-center gap-1">
                    <Radio className="w-2.5 h-2.5 text-cyan-400" /> C2:
                  </span>
                  <span
                    className={`font-semibold truncate max-w-[170px] ${
                      isGateway ? "text-amber-400" : "text-cyan-400"
                    }`}
                    title={route}
                  >
                    {route}
                  </span>
                </div>

                {/* Interactive Status & Battery Maintenance Actions */}
                {isReturning && (
                  <div className="mt-1.5 pt-1 border-t border-border/40">
                    <div className="text-[9.5px] font-mono text-amber-300 bg-amber-950/30 border border-amber-500/30 rounded px-2 py-1 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <RotateCcw className="w-3 h-3 animate-spin text-amber-400" /> Powrót do bazy (RTL)...
                      </span>
                      <span className="text-[8.5px] text-amber-400/80">Lądowanie</span>
                    </div>
                  </div>
                )}

                {isStandby && (
                  <div className="mt-1.5 pt-1 border-t border-border/40 flex flex-col gap-1.5">
                    {/* Wymiana baterii: dostępna dla KAŻDEGO drona w bazie, którego bateria nie jest pełna */}
                    {d.battery_pct < 99.5 && (
                      <Button
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSwapBattery && onSwapBattery(d.id);
                        }}
                        className={`w-full h-6.5 text-[10px] font-mono font-bold border gap-1.5 cursor-pointer shadow-sm transition-all ${
                          d.battery_pct < 30 || d.needs_battery_swap
                            ? "bg-amber-500/25 hover:bg-amber-500/40 border-amber-500/60 text-amber-200"
                            : "bg-amber-500/15 hover:bg-amber-500/25 border-amber-500/40 text-amber-300"
                        }`}
                        title={`Zatwierdź wymianę baterii na nowy pakiet 100% dla ${d.id}`}
                      >
                        <BatteryCharging className="w-3 h-3 text-amber-400 animate-pulse" />
                        <span>Wymień baterię (100%)</span>
                      </Button>
                    )}

                    {/* Wysłanie drona do misji: dostępne gdy poziom baterii jest bezpieczny (>= 25%) */}
                    {d.battery_pct >= 25.0 ? (
                      <Button
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRelaunchDrone && onRelaunchDrone(d.id);
                        }}
                        className="w-full h-6.5 text-[10px] font-mono font-bold bg-emerald-600/25 hover:bg-emerald-600/40 border border-emerald-500/60 text-emerald-300 gap-1.5 cursor-pointer shadow-[0_0_8px_rgba(16,185,129,0.2)] transition-all"
                        title={`Wyślij drona ${d.id} do realizacji misji`}
                      >
                        <Play className="w-3 h-3 fill-emerald-400 text-emerald-400" />
                        <span>Wyślij do realizacji misji</span>
                      </Button>
                    ) : (
                      <div className="text-[9px] font-mono text-rose-400 text-center py-0.5">
                        Bateria zbyt niska (&lt;25%) – wymagana wymiana przed startem
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
