"use client";

import React from "react";
import { Battery, BatteryCharging, BatteryWarning, Plane, ArrowRight, Radio, ShieldAlert } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export function SwarmPanel({ snapshot, onFocusDrone }) {
  const drones = snapshot?.drones || [];
  const mesh = snapshot?.mesh;
  const routes = mesh?.routes_to_gcs || {};

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
                  isGateway
                    ? "border-amber-500/40 bg-amber-950/15 hover:border-amber-400/60 shadow-[0_0_12px_rgba(255,183,0,0.06)]"
                    : "border-border/60 bg-background/60 hover:border-cyan-500/40 hover:bg-cyan-950/10"
                }`}
              >
                {/* Header: ID, Callsign & Role */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-xs font-bold text-foreground">
                      {d.id} <span className="text-muted-foreground font-normal text-[11px]">// {d.callsign}</span>
                    </span>
                  </div>
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
                      LiPo:
                    </span>
                    <span className={`font-bold ${batColor}`}>{d.battery_pct}%</span>
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
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
