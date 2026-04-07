"use client";
import { useState } from "react";

interface Action {
  id: string;
  title: string;
  subtitle: string;
  steps: string[];
}

interface Props {
  actions: Action[];
}

export default function ActionInbox({ actions: initial }: Props) {
  const [actions, setActions] = useState(initial);
  const [expanded, setExpanded] = useState<string | null>(null);

  const dismiss = (id: string) => {
    setActions((prev) => prev.filter((a) => a.id !== id));
    setExpanded(null);
  };

  return (
    <div className="flex flex-col gap-3">
      {actions.length === 0 && (
        <div className="text-center text-slate-600 text-sm py-12">All clear — no pending actions.</div>
      )}
      {actions.map((action, i) => {
        const isOpen = expanded === action.id;
        return (
          <div
            key={action.id}
            className="bg-[#0f1117] border border-slate-800 rounded-xl overflow-hidden transition-all"
          >
            {/* Card header */}
            <button
              onClick={() => setExpanded(isOpen ? null : action.id)}
              className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-800/40 transition-colors"
            >
              <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-amber-500/20 border border-amber-500/50 text-amber-400 text-[10px] font-bold flex items-center justify-center">
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-100 truncate">{action.title}</p>
                <p className="text-xs text-slate-500 mt-0.5">{action.subtitle}</p>
              </div>
              <span className="text-slate-600 text-xs mt-1">{isOpen ? "▲" : "▼"}</span>
            </button>

            {/* Chain-of-thought expand */}
            {isOpen && (
              <div className="px-4 pb-4 border-t border-slate-800">
                <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-3 mb-2">
                  Chain-of-Thought
                </p>
                <ol className="flex flex-col gap-2">
                  {action.steps.map((step, idx) => (
                    <li key={idx} className="flex gap-2 text-xs text-slate-300">
                      <span className="flex-shrink-0 w-4 h-4 rounded-full bg-slate-800 border border-slate-700 text-slate-400 text-[9px] font-bold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => dismiss(action.id)}
                    className="flex-1 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-xs font-bold transition-colors"
                  >
                    ✓ Approve &amp; Execute
                  </button>
                  <button
                    onClick={() => dismiss(action.id)}
                    className="flex-1 py-2 rounded-lg bg-red-900 hover:bg-red-700 text-red-300 text-xs font-bold transition-colors"
                  >
                    ✕ Reject
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
