"use client";

import React, { useState } from "react";
import { Plus, Radio, Crosshair } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function InjectVictimModal({ open, onOpenChange, onInject }) {
  const [signalType, setSignalType] = useState("WIFI_PROBE_REQ");
  const [lat, setLat] = useState("50.0614");
  const [lon, setLon] = useState("19.9366");
  const [txPower, setTxPower] = useState("17.0");
  const [loading, setLoading] = useState(false);

  // Generate random coordinate in crisis sector
  const randomizePosition = () => {
    const rLat = 50.0614 + (Math.random() - 0.5) * 0.015;
    const rLon = 19.9366 + (Math.random() - 0.5) * 0.015;
    setLat(rLat.toFixed(6));
    setLon(rLon.toFixed(6));
  };

  const handleInject = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onInject({
        lat: parseFloat(lat),
        lon: parseFloat(lon),
        signal_type: signalType,
        tx_power_dbm: parseFloat(txPower),
      });
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px] bg-card/95 border-border/60 text-foreground backdrop-blur-xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-rose-500" />
            <DialogTitle className="text-sm font-mono uppercase tracking-wide">
              Wstrzyknij Emiter Poszkodowanego
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground font-mono">
            Dodaje uwięziony telefon (Wi-Fi Probe Requests / LTE Direct Uplink) w strefie poszukiwań.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleInject} className="space-y-3 py-2 text-xs font-mono">
          <div>
            <label className="text-muted-foreground block mb-1">Typ Sygnału Radiowego</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSignalType("WIFI_PROBE_REQ")}
                className={`py-2 px-3 rounded border text-xs font-semibold transition-all ${
                  signalType === "WIFI_PROBE_REQ"
                    ? "border-cyan-500 bg-cyan-950/30 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.2)]"
                    : "border-border/60 text-muted-foreground hover:bg-muted"
                }`}
              >
                Wi-Fi Probe Req
              </button>
              <button
                type="button"
                onClick={() => setSignalType("LTE_DIRECT_UPLINK")}
                className={`py-2 px-3 rounded border text-xs font-semibold transition-all ${
                  signalType === "LTE_DIRECT_UPLINK"
                    ? "border-amber-500 bg-amber-950/30 text-amber-300 shadow-[0_0_8px_rgba(255,183,0,0.2)]"
                    : "border-border/60 text-muted-foreground hover:bg-muted"
                }`}
              >
                LTE Direct Uplink
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-muted-foreground block mb-1">Szerokość (Lat)</label>
              <input
                type="number"
                step="0.000001"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                className="w-full bg-background border border-border/60 rounded px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:border-rose-500"
                required
              />
            </div>
            <div>
              <label className="text-muted-foreground block mb-1">Długość (Lon)</label>
              <input
                type="number"
                step="0.000001"
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                className="w-full bg-background border border-border/60 rounded px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:border-rose-500"
                required
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={randomizePosition}
              className="text-[11px] text-cyan-400 hover:text-cyan-300 underline font-mono cursor-pointer"
            >
              🎲 Losuj pozycję w strefie
            </button>

            <div className="flex items-center gap-1.5">
              <label className="text-muted-foreground text-[10px]">Moc TX:</label>
              <input
                type="number"
                step="1"
                value={txPower}
                onChange={(e) => setTxPower(e.target.value)}
                className="w-14 bg-background border border-border/60 rounded px-1.5 py-1 text-center text-xs text-foreground"
              />
              <span className="text-[10px] text-muted-foreground">dBm</span>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-rose-600 hover:bg-rose-500 text-white font-mono text-xs gap-1.5 shadow-[0_0_12px_rgba(255,51,102,0.3)]"
            >
              <Crosshair className="w-3.5 h-3.5" />
              {loading ? "Wstrzykiwanie..." : "Rozpocznij Emisję"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
