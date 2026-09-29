"use client";

import React from "react";
import { Share2, Radio, Wifi, Zap, Activity } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function NetworkPanel({ snapshot }) {
  const mesh = snapshot?.mesh;
  const edges = mesh?.edges || [];
  const nodes = mesh?.nodes || [];

  return (
    <Card className="h-full min-h-0 flex flex-col border-border/50 bg-card/50 backdrop-blur-md shadow-lg overflow-hidden">
      <CardHeader className="px-3 py-2 shrink-0 border-b border-border/40 bg-muted/20 flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Share2 className="w-3.5 h-3.5 text-cyan-400" />
          <CardTitle className="text-xs font-mono font-bold tracking-wide uppercase text-foreground">
            Siatka Mesh ({edges.length} łączy)
          </CardTitle>
        </div>
        <Badge
          variant="outline"
          className={`text-[9px] font-mono px-1 py-0 h-4 ${
            mesh?.gcs_connected
              ? "border-emerald-500/40 bg-emerald-950/20 text-emerald-400"
              : "border-rose-500/40 bg-rose-950/20 text-rose-400"
          }`}
        >
          {mesh?.gcs_connected ? "GCS ONLINE" : "GCS OFFLINE"}
        </Badge>
      </CardHeader>

      <CardContent className="p-2 flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-2">
        {/* Network Metrics Overview */}
        <div className="grid grid-cols-2 gap-1.5 text-xs font-mono">
          <div className="bg-background/60 border border-border/40 p-1.5 rounded-md">
            <span className="text-[9px] text-muted-foreground block leading-tight">GŁÓWNY GATEWAY</span>
            <span className="font-bold text-amber-400 flex items-center gap-1 mt-0.5 text-[11px] leading-tight">
              <Zap className="w-2.5 h-2.5" />
              {mesh?.gateway_id || "BRAK (Autonomiczny)"}
            </span>
          </div>

          <div className="bg-background/60 border border-border/40 p-1.5 rounded-md">
            <span className="text-[9px] text-muted-foreground block leading-tight">ZASIĘGI ŁĄCZNOŚCI</span>
            <span className="font-bold text-cyan-400 block mt-0.5 text-[10px] leading-tight">
              P2P: {mesh?.mesh_range_m ? `${mesh.mesh_range_m}m` : "2500m"}
            </span>
            <span className="text-[9px] text-amber-400/90 block leading-tight">
              GCS: {mesh?.gcs_range_m ? `${mesh.gcs_range_m}m` : "5000m"}
            </span>
          </div>
        </div>

        {/* Edges Link Table */}
        <div className="space-y-1">
          <div className="text-[9px] font-mono text-muted-foreground uppercase flex items-center justify-between px-1">
            <span>Połączenie radiowe</span>
            <span>Dystans / Jakość</span>
          </div>

          {edges.length === 0 ? (
            <div className="text-center py-6 text-xs font-mono text-muted-foreground">
              Brak aktywnych łączy w zasięgu radiowym.
            </div>
          ) : (
            edges.map((e, idx) => {
              const isGcs = e.is_gateway_link || e.source === "GCS-BASE" || e.target === "GCS-BASE";
              const isHighQuality = e.quality_pct >= 50;

              return (
                <div
                  key={`${e.source}-${e.target}-${idx}`}
                  className={`p-1.5 rounded border text-[10px] font-mono flex items-center justify-between ${
                    isGcs
                      ? "border-amber-500/40 bg-amber-950/15"
                      : "border-border/40 bg-background/50 hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-center gap-1">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isGcs ? "bg-amber-400" : isHighQuality ? "bg-cyan-400" : "bg-muted-foreground"
                      }`}
                    />
                    <span className={`font-semibold ${isGcs ? "text-amber-300" : "text-foreground"}`}>
                      {e.source}
                    </span>
                    <span className="text-muted-foreground text-[9px]">↔</span>
                    <span className={`font-semibold ${isGcs ? "text-amber-300" : "text-foreground"}`}>
                      {e.target}
                    </span>
                  </div>

                  <div className="text-right">
                    <div className="font-semibold text-foreground text-[9.5px] leading-tight">{e.distance_m}m</div>
                    <div className="text-[8.5px] text-muted-foreground flex items-center gap-1 justify-end leading-tight">
                      <span>{e.rssi_dbm} dBm</span>
                      <span className={isHighQuality ? "text-emerald-400 font-bold" : "text-muted-foreground"}>
                        ({e.quality_pct}%)
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}
