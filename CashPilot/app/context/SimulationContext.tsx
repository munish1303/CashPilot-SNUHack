"use client";
import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";

type SimulationContextType = {
  daysOffset: number;
  simulatedDate: string;
  refreshKey: number;
  isSimulating: boolean;
  simulationError: string | null;
  triggerSimulation: (offset: number) => Promise<void>;
};

const SimulationContext = createContext<SimulationContextType | undefined>(undefined);

export function SimulationProvider({ children }: { children: ReactNode }) {
  const [daysOffset, setDaysOffset] = useState(0);
  const [simulatedDate, setSimulatedDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  const triggerSimulation = useCallback(async (offset: number) => {
    if (offset === daysOffset) return;
    if (offset < daysOffset) return;
    setIsSimulating(true);
    setSimulationError(null);

    try {
      const res = await fetch("/api/simulate/advance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days_offset: offset }),
      });

      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : "Failed to advance simulation.";
        setSimulationError(detail);
        return;
      }

      const simulatedAsOf = typeof payload?.simulated_as_of === "string"
        ? payload.simulated_as_of
        : new Date().toISOString();

      setDaysOffset(offset);
      setSimulatedDate(simulatedAsOf.split("T")[0]);
      // Bump refresh key so all consumers re-fetch
      setRefreshKey((k) => k + 1);
    } catch {
      setSimulationError("Backend unreachable. Showing last known simulation state.");
    } finally {
      setIsSimulating(false);
    }
  }, [daysOffset]);

  return (
    <SimulationContext.Provider value={{ daysOffset, simulatedDate, refreshKey, isSimulating, simulationError, triggerSimulation }}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulation() {
  const context = useContext(SimulationContext);
  if (!context) {
    throw new Error("useSimulation must be used within a SimulationProvider");
  }
  return context;
}
