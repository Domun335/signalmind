"use client";

import React, { useState, useEffect } from "react";
import { Settings2, Save, RotateCcw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function ConfigModal({ open, onOpenChange, onFetchConfig, onUpdateConfig }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    let ignore = false;
    if (open) {
      onFetchConfig()
        .then((data) => {
          if (!ignore && data) setConfig(data);
        })
        .finally(() => {
          if (!ignore) setLoading(false);
        });
    }
    return () => {
      ignore = true;
    };
  }, [open, onFetchConfig]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!config) return;
    setLoading(true);
    try {
      await onUpdateConfig(config);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2000);
      onOpenChange(false);
    } catch (err) {
      console.error("Save config error:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!config) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] bg-card/95 border-border/60 text-foreground backdrop-blur-xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-cyan-400" />
            <DialogTitle className="text-sm font-mono uppercase tracking-wide">
              Konfiguracja Parametrów Symulacji
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground font-mono">
            Parametry misji roju UAV, propagacji radiowej RF oraz taktycznej sieci MANET Mesh.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSave} className="space-y-3 py-2 text-xs font-mono max-h-[70vh] overflow-y-auto custom-scrollbar pr-1">
          {/* Swarm Settings */}
          <div className="border border-border/40 rounded p-2.5 bg-background/50 space-y-2">
            <div className="text-cyan-400 font-bold text-[11px] uppercase">Rój Bezzałogowców (Kinematyka)</div>
            
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Prędkość przelotowa (m/s)</label>
                <input
                  type="number"
                  step="0.5"
                  value={config.swarm?.cruise_speed_mps || 15.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      swarm: { ...config.swarm, cruise_speed_mps: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Wysokość poszukiwań (m)</label>
                <input
                  type="number"
                  step="5"
                  value={config.swarm?.search_altitude_m || 60.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      swarm: { ...config.swarm, search_altitude_m: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Rozstaw pasów (m)</label>
                <input
                  type="number"
                  step="10"
                  value={config.swarm?.lane_spacing_m || 120.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      swarm: { ...config.swarm, lane_spacing_m: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Tryb Planera Tras</label>
                <select
                  value={config.swarm?.planner_mode || "SYNCHRONIZED_FRONT"}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      swarm: { ...config.swarm, planner_mode: e.target.value },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                >
                  <option value="SYNCHRONIZED_FRONT">Synchronized Front</option>
                  <option value="RELAY_ANCHORED">Relay Anchored</option>
                  <option value="CLASSIC_BOUSTROPHEDON">Classic Lawnmower</option>
                </select>
              </div>
            </div>
          </div>

          {/* Mesh Radio Settings */}
          <div className="border border-border/40 rounded p-2.5 bg-background/50 space-y-2">
            <div className="text-amber-400 font-bold text-[11px] uppercase">Taktyczna Sieć P2P MANET Mesh</div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Zasięg P2P Mesh (m)</label>
                <input
                  type="number"
                  step="100"
                  value={config.mesh?.mesh_range_m || 2500.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      mesh: { ...config.mesh, mesh_range_m: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Zasięg stacji GCS (m)</label>
                <input
                  type="number"
                  step="100"
                  value={config.mesh?.gcs_range_m || 5000.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      mesh: { ...config.mesh, gcs_range_m: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Moc Nadawania TX (dBm)</label>
                <input
                  type="number"
                  step="1"
                  value={config.mesh?.tx_power_dbm || 30.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      mesh: { ...config.mesh, tx_power_dbm: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>

              <div>
                <label className="text-muted-foreground block text-[10px] mb-1">Czułość Odbiornika (dBm)</label>
                <input
                  type="number"
                  step="1"
                  value={config.mesh?.mesh_sensitivity_dbm || -97.0}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      mesh: { ...config.mesh, mesh_sensitivity_dbm: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full bg-background border border-border/60 rounded px-2 py-1 text-xs"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs gap-1.5 shadow-[0_0_12px_rgba(0,240,255,0.3)]"
            >
              <Save className="w-3.5 h-3.5" />
              {loading ? "Zapisywanie..." : savedSuccess ? "Zapisano Pomyślnie!" : "Zapisz i Zastosuj w Symulacji"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
