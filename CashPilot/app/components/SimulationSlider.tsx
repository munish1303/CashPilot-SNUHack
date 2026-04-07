"use client";
import { useState, useEffect } from "react";
import { useSimulation } from "../context/SimulationContext";
import { motion } from "framer-motion";
import { Clock, Zap } from "lucide-react";

export default function SimulationSlider() {
  const { daysOffset, simulatedDate, isSimulating, simulationError, triggerSimulation } = useSimulation();
  const [localOffset, setLocalOffset] = useState(daysOffset);

  useEffect(() => {
    setLocalOffset(daysOffset);
  }, [daysOffset]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localOffset !== daysOffset) {
        triggerSimulation(localOffset);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [localOffset, daysOffset, triggerSimulation]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextOffset = parseInt(e.target.value, 10);
    setLocalOffset(Math.max(daysOffset, nextOffset));
  };

  const pct = (localOffset / 30) * 100;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="mx-3 mb-3 rounded-2xl bg-gradient-to-b from-slate-50 to-white border border-slate-200/60 p-4 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-6 h-6 rounded-lg flex items-center justify-center ${isSimulating ? "bg-amber-100" : "bg-indigo-50"}`}>
            {isSimulating ? (
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                <Zap size={12} className="text-amber-600" />
              </motion.div>
            ) : (
              <Clock size={12} className="text-indigo-600" />
            )}
          </div>
          <span className="text-[11px] font-semibold text-slate-700 tracking-wide">Timeline</span>
        </div>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-md border transition-colors ${
            isSimulating
              ? "bg-amber-50 text-amber-700 border-amber-200"
              : localOffset > 0
                ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                : "bg-slate-50 text-slate-500 border-slate-200"
          }`}
        >
          {isSimulating ? "Simulating..." : `+${localOffset}d`}
        </span>
      </div>

      {/* Date display */}
      <div className="mb-4 text-center">
        <p className="text-lg font-bold text-slate-800 tabular-nums tracking-tight">{simulatedDate}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">
          {localOffset === 0 ? "Current date" : `${localOffset} days from today`}
        </p>
      </div>

      {/* Custom slider */}
      <div className="relative group">
        <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400"
            animate={{ width: `${pct}%` }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          />
        </div>
        <input
          type="range"
          min={daysOffset}
          max="30"
          step="1"
          value={localOffset}
          onChange={handleChange}
          disabled={isSimulating}
          className="sim-slider absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-wait"
        />
        {/* Thumb indicator */}
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 border-indigo-500 shadow-md pointer-events-none"
          animate={{ left: `calc(${pct}% - 8px)` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {isSimulating && (
            <motion.div
              className="absolute inset-0 rounded-full border-2 border-indigo-400"
              animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
          )}
        </motion.div>
      </div>

      {/* Scale labels */}
      <div className="flex justify-between mt-2 text-[9px] text-slate-400 font-medium px-0.5">
        <span>Today</span>
        <span>+1</span>
        <span>+10</span>
        <span>+20</span>
        <span>+30</span>
      </div>

      <p className="mt-1 text-[9px] text-slate-400">Moves in 1-day increments.</p>

      {simulationError && (
        <p className="mt-2 text-[10px] text-amber-600">{simulationError}</p>
      )}
    </motion.div>
  );
}
