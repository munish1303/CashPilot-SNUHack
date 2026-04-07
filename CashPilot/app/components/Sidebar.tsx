"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, BarChart2, Upload, Inbox, Wifi } from "lucide-react";
import { useState, useEffect } from "react";
import { useSimulation } from "../context/SimulationContext";

import SimulationSlider from "./SimulationSlider";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/ingestion", label: "Ingestion", icon: Upload },
  { href: "/inbox", label: "Action Inbox", icon: Inbox },
];

export default function Sidebar() {
  const path = usePathname();
  const { refreshKey } = useSimulation();
  const [actionCount, setActionCount] = useState<number>(0);

  useEffect(() => {
    async function fetchCount() {
      try {
        const res = await fetch("/api/dashboard");
        if (res.ok) {
          const json = await res.json();
          setActionCount(json.actionCount || 0);
        }
      } catch {}
    }
    fetchCount();
  }, [refreshKey]);

  return (
    <aside className="w-60 shrink-0 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100">
        <span className="text-sm font-bold tracking-tight text-gray-900">Cash<span className="text-indigo-600">Pilot</span></span>
        <p className="text-[10px] text-gray-400 mt-0.5 uppercase tracking-widest">Autopilot Command Center</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"
              }`}
            >
              <Icon size={16} strokeWidth={active ? 2.5 : 1.8} />
              {label}
              {label === "Action Inbox" && actionCount > 0 && (
                <span className="ml-auto bg-red-100 text-red-600 text-[10px] font-bold px-1.5 py-0.5 rounded-full">{actionCount}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Simulation Slider */}
      <SimulationSlider />

      {/* Footer */}
      <div className="px-4 py-4 border-t border-gray-100">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-bold">A</div>
          <div>
            <p className="text-xs font-semibold text-gray-700">Admin User</p>
            <p className="text-[10px] text-gray-400">admin@cashpilot.ai</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Wifi size={11} className="text-emerald-500" />
          <span className="text-[10px] text-emerald-600 font-medium">System Status: Online</span>
        </div>
      </div>
    </aside>
  );
}

