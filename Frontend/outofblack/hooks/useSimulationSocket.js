"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/telemetry";

export function useSimulationSocket() {
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [speedMultiplier, setSpeedMultiplier] = useState(1.0);
  const [error, setError] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isMountedRef = useRef(true);

  // Connect to telemetry WebSocket stream
  const connect = useCallback(() => {
    if (!isMountedRef.current) return;
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setConnecting(true);
    setError(null);

    try {
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        if (!isMountedRef.current) return;
        setConnected(true);
        setConnecting(false);
        setError(null);
        console.log("[OutOfBlack] Telemetry WebSocket connected.");
      };

      socket.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          setSnapshot(data);
        } catch (err) {
          console.error("[OutOfBlack] Failed to parse telemetry payload:", err);
        }
      };

      socket.onerror = (err) => {
        console.warn("[OutOfBlack] WebSocket error:", err);
      };

      socket.onclose = () => {
        if (!isMountedRef.current) return;
        setConnected(false);
        setConnecting(false);
        socketRef.current = null;
        console.log("[OutOfBlack] WebSocket disconnected. Reconnecting in 2s...");
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };
    } catch (err) {
      setConnected(false);
      setConnecting(false);
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    }
  }, []);

  // Fetch initial REST snapshot as fallback
  const fetchInitialState = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/state`);
      if (res.ok) {
        const data = await res.json();
        setSnapshot(data);
      }
    } catch (err) {
      console.warn("[OutOfBlack] Initial state fetch error:", err);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    fetchInitialState();
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect, fetchInitialState]);

  // REST Control Actions (stable callbacks)
  const startMission = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/start`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("Start error:", err);
    }
  }, []);

  const pauseMission = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/pause`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("Pause error:", err);
    }
  }, []);

  const resumeMission = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/resume`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("Resume error:", err);
    }
  }, []);

  const resetMission = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/reset`, { method: "POST" });
      setSpeedMultiplier(1.0);
      return await res.json();
    } catch (err) {
      console.error("Reset error:", err);
    }
  }, []);

  const setSpeed = useCallback(async (multiplier) => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/speed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ multiplier }),
      });
      const data = await res.json();
      if (data.status === "SUCCESS") {
        setSpeedMultiplier(multiplier);
      }
      return data;
    } catch (err) {
      console.error("Set speed error:", err);
    }
  }, []);

  const injectVictim = useCallback(async ({ lat, lon, signal_type = "WIFI_PROBE_REQ", tx_power_dbm = 16.0 }) => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/inject-poi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lon, signal_type, tx_power_dbm }),
      });
      return await res.json();
    } catch (err) {
      console.error("Inject victim error:", err);
    }
  }, []);

  const fetchSimulationConfig = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/config`);
      if (res.ok) return await res.json();
    } catch (err) {
      console.error("Fetch simulation config error:", err);
    }
    return null;
  }, []);

  const updateSimulationConfig = useCallback(async (newConfig) => {
    try {
      const res = await fetch(`${BACKEND_URL}/simulation/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newConfig),
      });
      return await res.json();
    } catch (err) {
      console.error("Update simulation config error:", err);
    }
  }, []);

  const fetchConfig = fetchSimulationConfig;
  const updateConfig = updateSimulationConfig;

  return {
    snapshot,
    connected,
    connecting,
    speedMultiplier,
    error,
    startMission,
    pauseMission,
    resumeMission,
    resetMission,
    setSpeed,
    injectVictim,
    fetchConfig,
    updateConfig,
    fetchSimulationConfig,
    updateSimulationConfig,
  };
}
