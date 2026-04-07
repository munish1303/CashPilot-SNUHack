"use client";
import { useState, useEffect } from "react";
import { useSimulation } from "../context/SimulationContext";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, CartesianGrid, Legend,
} from "recharts";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import { Zap, Shield, CheckCircle2, AlertTriangle, Clock } from "lucide-react";

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

const tierStyle: Record<number, { bg: string; text: string; label: string }> = {
  0: { bg: "bg-red-100", text: "text-red-700", label: "Locked" },
  1: { bg: "bg-amber-100", text: "text-amber-700", label: "Penalty" },
  2: { bg: "bg-blue-100", text: "text-blue-700", label: "Relational" },
  3: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Flexible" },
};

type AnalyticsData = {
  cashFlow: { day: string; standard: number; phantom: number }[];
  vendors: { name: string; goodwill: number }[];
  monteCarlo: { simulations: number; probability: number; p10: number; median: number; p90: number };
  optimization?: OptimizationData | null;
};

type OptimizationObligation = {
  obligation_id?: string;
  entity_name: string;
  ontology_tier: number;
  goodwill_score?: number;
  original_amount: number;
  pay_now: number;
  delay_amount: number;
  new_due_date: string;
  original_due: string;
  estimated_cost: number;
};

type OptimizationData = {
  status: string;
  breach_prevented?: boolean;
  error?: string;
  optimized_obligations?: OptimizationObligation[];
  total_delayed?: number;
  projected_savings?: number;
};

export default function AnalyticsPage() {
  const { refreshKey, isSimulating, simulatedDate } = useSimulation();
  const [data, setData] = useState<AnalyticsData | null>(null);

  useEffect(() => {
    async function fetchAnalytics() {
      try {
        const res = await fetch(`/api/analytics?refresh=${refreshKey}`, {
          cache: "no-store",
          headers: { "Cache-Control": "no-cache" },
        });
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (err) {
        console.error("Failed to fetch analytics", err);
      }
    }
    fetchAnalytics();
  }, [refreshKey]);

  if (!data) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-400 mt-1">Loading live data from Supabase…</p>
        </div>
        <div className="shimmer h-72 rounded-2xl mb-6" />
        <div className="grid grid-cols-2 gap-6">
          <div className="shimmer h-64 rounded-2xl" />
          <div className="shimmer h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  const { cashFlow, monteCarlo, vendors, optimization } = data;
  const radarData = vendors.map((v) => ({ vendor: v.name, score: v.goodwill }));

  // Check if breach occurs
  const hasLiquidityBreach = cashFlow.some(d => d.standard < 0 || d.phantom < 0);
  
  // Only show actionable vendors (those with delay_amount > 0)
  const actionableVendors = optimization?.optimized_obligations?.filter(
    (ob: OptimizationObligation) => ob.delay_amount > 0
  ) || [];

  return (
    <div className={`p-8 max-w-5xl mx-auto transition-opacity duration-300 ${isSimulating ? "opacity-60" : "opacity-100"}`}>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-sm text-gray-400 mt-1">
          Live from Supabase · Simulated as of {simulatedDate}
        </p>
      </div>

      {/* Main dual-line chart */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6 fade-in">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-sm font-semibold text-gray-800">30-Day Cash Projection</p>
            <p className="text-xs text-gray-400 mt-0.5">Standard vs. Phantom (Liquidity Breach visible)</p>
          </div>
          {hasLiquidityBreach && (
            <span className="text-[10px] bg-red-50 border border-red-200 text-red-600 font-semibold px-2.5 py-1 rounded-full uppercase tracking-wide">
              Liquidity Breach Detected
            </span>
          )}
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={cashFlow} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="day" tick={{ fill: "#94a3b8", fontSize: 10 }} tickLine={false} axisLine={false} interval={4} />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              width={40}
            />
            <Tooltip
              contentStyle={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, fontSize: 11 }}
              formatter={(v, name) => [`$${Number(v).toLocaleString()}`, name === "standard" ? "Standard Balance" : "Phantom Usable"]}
            />
            <Legend
              formatter={(v) => v === "standard" ? "Standard Balance" : "Phantom Usable"}
              wrapperStyle={{ fontSize: 11, color: "#64748b" }}
            />
            <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1.5} label={{ value: "$0 Breach", fill: "#ef4444", fontSize: 10 }} />
            <Line type="monotone" dataKey="standard" stroke="#cbd5e1" strokeWidth={2} dot={false} strokeDasharray="6 3" />
            <Line type="monotone" dataKey="phantom" stroke="#6366f1" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Monte Carlo + Goodwill Radar */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Monte Carlo */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 fade-in">
          <p className="text-sm font-semibold text-gray-800 mb-1">Monte Carlo Engine</p>
          <p className="text-xs text-gray-400 mb-5">{monteCarlo.simulations.toLocaleString()} simulations of invoice payment latency</p>

          {/* Big probability ring */}
          <div className="flex items-center gap-6 mb-6">
            <div className="relative w-24 h-24 shrink-0">
              <svg viewBox="0 0 36 36" className="w-24 h-24 -rotate-90">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f1f5f9" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15.9" fill="none"
                  stroke={monteCarlo.probability >= 70 ? "#10b981" : monteCarlo.probability >= 40 ? "#f59e0b" : "#ef4444"}
                  strokeWidth="3"
                  strokeDasharray={`${monteCarlo.probability} ${100 - monteCarlo.probability}`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xl font-black text-gray-800">{monteCarlo.probability}%</span>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-gray-700">Probability of Survival</p>
              <p className="text-[11px] text-gray-400">Based on invoice latency variance across {monteCarlo.simulations.toLocaleString()} runs</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "P10 (Bear)", value: monteCarlo.p10, color: "text-red-500" },
              { label: "Median", value: monteCarlo.median, color: "text-gray-700" },
              { label: "P90 (Bull)", value: monteCarlo.p90, color: "text-emerald-500" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-gray-50 rounded-xl p-3 text-center">
                <p className="text-[10px] text-gray-400 mb-1">{label}</p>
                <p className={`text-sm font-bold ${color}`}>${value.toLocaleString()}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Goodwill Radar */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 fade-in">
          <p className="text-sm font-semibold text-gray-800 mb-1">Vendor Goodwill Radar</p>
          <p className="text-xs text-gray-400 mb-4">Ontology health scores by vendor · Live from Supabase</p>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
              <PolarGrid stroke="#f1f5f9" />
              <PolarAngleAxis dataKey="vendor" tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#cbd5e1", fontSize: 9 }} />
              <Radar name="Goodwill" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* LP Optimization Strategy */}
      {optimization && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 fade-in">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center">
                <Zap size={16} className="text-indigo-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-800">LP Optimization Strategy</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {optimization.status === "UNAVAILABLE"
                    ? "Optimization engine unavailable"
                    : optimization.status === "SUCCESS"
                    ? `${actionableVendors.length} vendor${actionableVendors.length !== 1 ? "s" : ""} with recommended payment deferrals`
                    : optimization.status === "NO_OPTIMIZATION_NEEDED"
                    ? "All obligations covered — no optimization needed"
                    : optimization.status === "OPTIMIZATION_FAILED"
                    ? "Optimization computation failed"
                    : "Computing optimization..."}
                </p>
              </div>
            </div>
            {optimization.status === "SUCCESS" && optimization.breach_prevented && (
              <span className="text-[10px] bg-emerald-50 border border-emerald-200 text-emerald-600 font-semibold px-2.5 py-1 rounded-full uppercase tracking-wide flex items-center gap-1">
                <Shield size={10} /> Breach Prevented
              </span>
            )}
          </div>

          {optimization.status === "UNAVAILABLE" && (
            <div className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 flex items-center gap-3">
              <AlertTriangle size={16} className="text-gray-400 shrink-0" />
              <p className="text-xs text-gray-600">
                LP optimization engine is currently unavailable. Check backend logs for details.
              </p>
            </div>
          )}

          {optimization.status === "NO_OPTIMIZATION_NEEDED" && (
            <div className="bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-3 flex items-center gap-3">
              <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
              <p className="text-xs text-emerald-700">
                Current balance fully covers all upcoming obligations within the 14-day horizon. No payment deferrals needed.
              </p>
            </div>
          )}

          {optimization.status === "OPTIMIZATION_FAILED" && (
            <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 flex items-center gap-3">
              <AlertTriangle size={16} className="text-amber-500 shrink-0" />
              <p className="text-xs text-amber-700">
                Optimization failed: {optimization.error || "Unknown error"}
              </p>
            </div>
          )}

          {actionableVendors.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3 mb-2">
                <p className="text-xs text-indigo-700">
                  <span className="font-semibold">Linear Programming Solution:</span> Minimizes late fees + goodwill damage 
                  while maintaining positive cash balance. Tier-based constraints ensure critical obligations (taxes, payroll) are never delayed.
                </p>
              </div>

              {actionableVendors.map((ob: OptimizationObligation, idx: number) => {
                const ts = tierStyle[ob.ontology_tier] || tierStyle[3];
                return (
                  <div key={ob.obligation_id || idx} className="bg-gray-50 rounded-xl border border-gray-100 px-5 py-4">
                    {/* Vendor info */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-gray-800">{ob.entity_name}</p>
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${ts.bg} ${ts.text} uppercase tracking-wide`}>
                          Tier {ob.ontology_tier} · {ts.label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">
                        Goodwill: {ob.goodwill_score ?? "N/A"}/100
                      </p>
                    </div>

                    {/* Payment strategy */}
                    <div className="grid grid-cols-4 gap-3">
                      <div className="bg-white rounded-lg p-3 text-center border border-gray-200">
                        <p className="text-[9px] text-gray-400 mb-1 uppercase tracking-wide">Original Amount</p>
                        <p className="text-sm font-bold text-gray-700">{fmt(Math.abs(ob.original_amount))}</p>
                      </div>
                      <div className="bg-emerald-50 rounded-lg p-3 text-center border border-emerald-200">
                        <p className="text-[9px] text-emerald-600 mb-1 uppercase tracking-wide">Pay Now</p>
                        <p className="text-sm font-bold text-emerald-700">{fmt(ob.pay_now)}</p>
                      </div>
                      <div className="bg-amber-50 rounded-lg p-3 text-center border border-amber-200">
                        <p className="text-[9px] text-amber-600 mb-1 uppercase tracking-wide">Delay</p>
                        <p className="text-sm font-bold text-amber-700">{fmt(ob.delay_amount)}</p>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3 text-center border border-gray-200">
                        <p className="text-[9px] text-gray-400 mb-1 uppercase tracking-wide flex items-center justify-center gap-0.5">
                          <Clock size={8} /> New Due
                        </p>
                        <p className="text-xs font-semibold text-gray-600">{new Date(ob.new_due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
                      </div>
                    </div>

                    <div className="mt-2 text-xs text-gray-500">
                      Original due: {new Date(ob.original_due).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} · 
                      Est. cost: {fmt(ob.estimated_cost)}
                    </div>
                  </div>
                );
              })}

              {/* Summary footer */}
              {optimization.total_delayed > 0 && (
                <div className="flex items-center justify-between bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3 mt-1">
                  <p className="text-xs text-indigo-700 font-medium">
                    Total deferred: <span className="font-bold">{fmt(optimization.total_delayed)}</span>
                  </p>
                  <p className="text-xs text-indigo-500">
                    Projected savings: {fmt(optimization.projected_savings)} vs. full penalties
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
