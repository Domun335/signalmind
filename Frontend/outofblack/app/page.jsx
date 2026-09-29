"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useSimulationSocket } from "@/hooks/useSimulationSocket";
import { TopNav } from "@/components/dashboard/TopNav";
import { SimulationContextBar } from "@/components/dashboard/SimulationContextBar";
import { SimulationStudio } from "@/components/setup/SimulationStudio";
import { SwarmPanel } from "@/components/dashboard/SwarmPanel";
import { SignalsPanel } from "@/components/dashboard/SignalsPanel";
import { NetworkPanel } from "@/components/dashboard/NetworkPanel";
import { InjectVictimModal } from "@/components/dashboard/InjectVictimModal";
import { ConfigModal } from "@/components/dashboard/ConfigModal";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Crosshair, Share2 } from "lucide-react";

// Dynamically import TacticalMap to disable SSR for Leaflet
const TacticalMap = dynamic(
  () => import("@/components/dashboard/TacticalMap").then((mod) => mod.TacticalMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-0 flex flex-col items-center justify-center bg-[#090d16] border border-border/50 rounded-lg text-cyan-400 font-mono text-xs gap-2">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span>Ładowanie silnika taktycznego GIS Leaflet...</span>
      </div>
    ),
  }
);

export default function Home() {
  const {
    snapshot,
    connected,
    connecting,
    speedMultiplier,
    startMission,
    pauseMission,
    resumeMission,
    resetMission,
    setSpeed,
    injectVictim,
    fetchSimulationConfig,
    updateSimulationConfig,
  } = useSimulationSocket();

  // Dual-Mode Tactical Workspace: "setup" (Setup Studio) vs "operator" (Live Operator Console)
  const [activeMode, setActiveMode] = useState("setup");
  const [simulationConfig, setSimulationConfig] = useState(null);
  const [focusedCoordinate, setFocusedCoordinate] = useState(null);
  const [injectModalOpen, setInjectModalOpen] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);

  // Load active simulation configuration from backend on mount
  useEffect(() => {
    let isMounted = true;
    fetchSimulationConfig().then((cfg) => {
      if (isMounted && cfg) {
        setSimulationConfig(cfg);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [fetchSimulationConfig]);

  const handleSaveSimulationConfig = async (newConfig) => {
    const res = await updateSimulationConfig(newConfig);
    setSimulationConfig(newConfig);
    return res;
  };

  const handleLaunchOperator = async (newConfig) => {
    await updateSimulationConfig(newConfig);
    setSimulationConfig(newConfig);
    setActiveMode("operator");
  };

  const handleModeChange = async (newMode) => {
    if (newMode === "operator" && activeMode === "setup" && simulationConfig) {
      await updateSimulationConfig(simulationConfig);
    }
    setActiveMode(newMode);
  };

  return (
    <div className="h-screen max-h-screen w-screen overflow-hidden flex flex-col bg-background text-foreground">
      {/* 1. Tactical Command Header with Mode Switcher */}
      <TopNav
        mode={activeMode}
        onModeChange={handleModeChange}
        snapshot={snapshot}
        connected={connected}
        connecting={connecting}
        speedMultiplier={speedMultiplier}
        onStart={startMission}
        onPause={pauseMission}
        onResume={resumeMission}
        onReset={resetMission}
        onSetSpeed={setSpeed}
        onOpenInject={() => setInjectModalOpen(true)}
        onOpenConfig={() => setConfigModalOpen(true)}
      />

      {/* 2. Dual-Mode Workspace: 1. Setup Studio OR 2. Embedded Operator Console */}
      {activeMode === "setup" ? (
        <div className="flex-1 min-h-0 overflow-hidden">
          <SimulationStudio
            initialConfig={simulationConfig}
            onSaveConfig={handleSaveSimulationConfig}
            onLaunchOperator={handleLaunchOperator}
            onChangeConfig={(cfg) => setSimulationConfig(cfg)}
          />
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {/* Sub-Header: Active Simulation Context Bar */}
          <SimulationContextBar
            config={simulationConfig}
            snapshot={snapshot}
            onOpenSetup={() => setActiveMode("setup")}
          />

          {/* 3-Column Zero-Scroll Tactical Command Canvas */}
          <main className="flex-1 min-h-0 p-2 md:p-2.5 grid grid-cols-1 lg:grid-cols-12 gap-2 md:gap-2.5 overflow-hidden">
            {/* Left Column: UAV Swarm Telemetry & LiPo Battery Monitor (3 cols on lg) */}
            <section className="lg:col-span-3 h-full min-h-0 flex flex-col overflow-hidden">
              <SwarmPanel snapshot={snapshot} onFocusDrone={setFocusedCoordinate} />
            </section>

            {/* Center Column: Interactive Tactical GIS Map (6 cols on lg) */}
            <section className="lg:col-span-6 h-full min-h-0 flex flex-col overflow-hidden">
              <TacticalMap
                snapshot={snapshot}
                focusedCoordinate={focusedCoordinate}
                config={simulationConfig}
              />
            </section>

            {/* Right Column: Signals / Victims & MANET Mesh Topology (3 cols on lg) */}
            <section className="lg:col-span-3 h-full min-h-0 flex flex-col overflow-hidden">
              <Tabs defaultValue="signals" className="h-full min-h-0 flex flex-col overflow-hidden">
                <TabsList className="grid grid-cols-2 mb-1.5 shrink-0 bg-muted/40 border border-border/40 p-0.5 h-8">
                  <TabsTrigger
                    value="signals"
                    className="text-[11px] font-mono font-bold gap-1 py-1 data-[state=active]:bg-rose-950/40 data-[state=active]:text-rose-400 data-[state=active]:border-rose-500/40"
                  >
                    <Crosshair className="w-3 h-3 text-rose-400" />
                    Sygnały ({snapshot?.pois?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger
                    value="network"
                    className="text-[11px] font-mono font-bold gap-1 py-1 data-[state=active]:bg-cyan-950/40 data-[state=active]:text-cyan-400 data-[state=active]:border-cyan-500/40"
                  >
                    <Share2 className="w-3 h-3 text-cyan-400" />
                    Siatka Mesh
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="signals" className="flex-1 min-h-0 mt-0 overflow-hidden">
                  <SignalsPanel snapshot={snapshot} onFocusPOI={setFocusedCoordinate} />
                </TabsContent>

                <TabsContent value="network" className="flex-1 min-h-0 mt-0 overflow-hidden">
                  <NetworkPanel snapshot={snapshot} />
                </TabsContent>
              </Tabs>
            </section>
          </main>
        </div>
      )}

      {/* 3. Action Modals */}
      <InjectVictimModal
        open={injectModalOpen}
        onOpenChange={setInjectModalOpen}
        onInject={injectVictim}
      />

      <ConfigModal
        open={configModalOpen}
        onOpenChange={setConfigModalOpen}
        onFetchConfig={fetchSimulationConfig}
        onUpdateConfig={handleSaveSimulationConfig}
      />
    </div>
  );
}
