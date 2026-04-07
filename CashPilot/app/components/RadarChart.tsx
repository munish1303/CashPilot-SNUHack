"use client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface Props {
  data: { day: string; standard: number; phantom: number }[];
  survivalProbability: number;
}

export default function RadarChart({ data, survivalProbability }: Props) {
  return (
    <div className="relative bg-[#0f1117] border border-slate-800 rounded-xl p-4 h-72">
      <div className="absolute top-3 right-3 z-10 bg-red-950 border border-red-700 rounded-lg px-3 py-1 text-xs font-bold text-red-400">
        Survival Probability: {survivalProbability}%
      </div>
      <p className="text-xs text-slate-500 mb-3 uppercase tracking-widest">30-Day Cash Radar</p>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="day"
            tick={{ fill: "#475569", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            interval={4}
          />
          <YAxis
            tick={{ fill: "#475569", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            width={36}
          />
          <Tooltip
            contentStyle={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8", fontSize: 11 }}
            formatter={(value, name) => [
              `$${Number(value).toLocaleString()}`,
              name === "standard" ? "Total Balance" : "Phantom Usable",
            ]}
          />
          <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} />
          <Line
            type="monotone"
            dataKey="standard"
            stroke="#334155"
            strokeWidth={1.5}
            dot={false}
            strokeDasharray="5 3"
          />
          <Line
            type="monotone"
            dataKey="phantom"
            stroke="#22c55e"
            strokeWidth={2.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
