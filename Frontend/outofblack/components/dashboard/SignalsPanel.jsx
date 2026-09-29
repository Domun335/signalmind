"use client";

import React from "react";
import { Radio, Crosshair, Wifi, Smartphone, AlertCircle, Signal } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export function SignalsPanel({ snapshot, onFocusPOI }) {
  const pois = snapshot?.pois || [];

  return (
    <Card className="h-full min-h-0 flex flex-col border-border/50 bg-card/50 backdrop-blur-md shadow-lg overflow-hidden">
      <CardHeader className="px-3 py-2 shrink-0 border-b border-border/40 bg-muted/20 flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Crosshair className="w-3.5 h-3.5 text-rose-500" />
          <CardTitle className="text-xs font-mono font-bold tracking-wide uppercase text-foreground">
            Wykryte Sygnały ({pois.length})
          </CardTitle>
        </div>
        <Badge variant="outline" className="text-[9px] font-mono border-rose-500/40 bg-rose-950/20 text-rose-400 px-1 py-0 h-4">
          WCL + NLS
        </Badge>
      </CardHeader>

      <CardContent className="p-2 flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-2">
        {pois.length === 0 ? (
          <div className="h-28 flex flex-col items-center justify-center text-xs font-mono text-muted-foreground text-center gap-1.5 p-3">
            <Radio className="w-5 h-5 text-muted-foreground/40 animate-pulse" />
            <span>Skanowanie pasm 2.4 GHz i LTE w strefie blackoutu...</span>
          </div>
        ) : (
          pois.map((poi) => {
            const confPct = Math.round(poi.confidence * 100);
            const isWifi = poi.signal_type === "WIFI_PROBE_REQ";

            return (
              <div
                key={poi.anonymized_id}
                onClick={() => onFocusPOI && onFocusPOI({ lat: poi.est_lat, lon: poi.est_lon })}
                className="p-2 rounded-lg border border-rose-500/30 bg-rose-950/10 hover:border-rose-400/60 hover:bg-rose-900/20 transition-all cursor-pointer select-none shadow-[0_0_10px_rgba(255,51,102,0.05)]"
              >
                {/* Header: Hash ID & Confidence */}
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-bold text-rose-400 flex items-center gap-1">
                    <Crosshair className="w-3 h-3 text-rose-500" />
                    {poi.anonymized_id}
                  </span>
                  <Badge
                    variant="outline"
                    className="text-[8.5px] font-mono font-bold border-emerald-500/40 bg-emerald-950/30 text-emerald-400 px-1 py-0 h-3.5 leading-none"
                  >
                    {confPct}% PEWNOŚCI
                  </Badge>
                </div>

                {/* Confidence Bar */}
                <div className="space-y-0.5 mb-1.5">
                  <Progress value={confPct} className="h-1 bg-muted/60" indicatorClassName="bg-rose-500" />
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-3 gap-1 text-[9.5px] font-mono text-muted-foreground bg-muted/30 p-1 rounded mb-1">
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">BŁĄD CEP</span>
                    <span className="font-semibold text-rose-300">±{poi.uncertainty_radius_m.toFixed(0)}m</span>
                  </div>
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">IMPULSY</span>
                    <span className="font-semibold text-foreground">{poi.detections_count}</span>
                  </div>
                  <div>
                    <span className="text-[8.5px] text-muted-foreground/70 block leading-tight">RSSI</span>
                    <span className="font-semibold text-foreground">{poi.last_rssi_dbm} dBm</span>
                  </div>
                </div>

                {/* Footer: Protocol & Sniffing Swarm Nodes */}
                <div className="flex items-center justify-between text-[9px] font-mono pt-1 border-t border-border/30 text-muted-foreground">
                  <span className="flex items-center gap-1">
                    {isWifi ? <Wifi className="w-2.5 h-2.5 text-cyan-400" /> : <Smartphone className="w-2.5 h-2.5 text-amber-400" />}
                    {isWifi ? "Wi-Fi Probe" : "LTE Uplink"}
                  </span>
                  <span className="truncate max-w-[140px] text-muted-foreground/80">
                    Odbiór: {poi.sniffed_by_drones.join(", ")}
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
