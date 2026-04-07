"use client";
import { useState, useEffect } from "react";
import { useSimulation } from "../context/SimulationContext";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, X, CheckCircle2, XCircle, Zap, Mail, FileText } from "lucide-react";

export type Step = { label: string; detail: string };

type RawPayload = Record<string, unknown>;

export type Action = {
  id: string;
  title: string;
  subtitle: string;
  priority: "critical" | "high" | "medium";
  steps: Step[];
  payload: Step[];
  rawPayload?: RawPayload;
  executionType?: string;
  rawActionType?: string;
  canGenerateDrafts?: boolean;
  hasCommunicationDraft?: boolean;
};

type InboxApiLog = {
  id: string;
  actionType: string;
  summary: string;
  priority: "critical" | "high" | "medium";
  chainOfThought?: Step[];
  payload?: Step[];
  rawPayload?: RawPayload;
  executionType?: string;
  rawActionType?: string;
  canGenerateDrafts?: boolean;
  hasCommunicationDraft?: boolean;
};

const priorityStyles: Record<string, { badge: string; dot: string }> = {
  critical: { badge: "bg-red-50 text-red-600 border-red-200", dot: "bg-red-500" },
  high:     { badge: "bg-amber-50 text-amber-600 border-amber-200", dot: "bg-amber-500" },
  medium:   { badge: "bg-blue-50 text-blue-600 border-blue-200", dot: "bg-blue-400" },
};

function getEmailField(payload: RawPayload | undefined, key: string) {
  const value = payload?.[key];
  return typeof value === "string" ? value : "";
}

function formatEmailBody(body: string) {
  return body
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line, idx, arr) => !(line === "" && arr[idx - 1] === ""));
}

export default function InboxPage() {
  const { refreshKey } = useSimulation();
  const [actions, setActions] = useState<Action[]>([]);
  const [selected, setSelected] = useState<Action | null>(null);
  const [isGeneratingDrafts, setIsGeneratingDrafts] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function fetchInbox() {
    try {
      const res = await fetch("/api/inbox");
      if (res.ok) {
        const json = await res.json();
        const inboxLogs: InboxApiLog[] = Array.isArray(json.inbox) ? json.inbox : [];
          const mapped: Action[] = inboxLogs.map((log) => ({
          id: log.id,
          title: log.actionType,
          subtitle: log.summary,
          priority: log.priority,
          steps: Array.isArray(log.chainOfThought) ? log.chainOfThought : [],
          payload: Array.isArray(log.payload) ? log.payload : [],
          rawPayload: log.rawPayload,
          executionType: log.executionType,
          rawActionType: log.rawActionType,
          canGenerateDrafts: Boolean(log.canGenerateDrafts),
          hasCommunicationDraft: Boolean(log.hasCommunicationDraft),
        }));
        setActions(mapped);
      }
    } catch (err) {
      console.error("Failed to fetch inbox:", err);
    }
  }

  useEffect(() => {
    fetchInbox();
  }, [refreshKey]);

  const dismiss = async (id: string) => {
    setActions((prev) => prev.filter((a) => a.id !== id));
    setSelected(null);
  };

  const generateDrafts = async (generateAll = false) => {
    setIsGeneratingDrafts(true);
    setFeedback(null);

    try {
      const res = await fetch("/api/ai/auto-generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_action_id: generateAll ? null : selected?.id ?? null,
          generate_all: generateAll,
        }),
      });

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(json?.detail || "Failed to generate AI drafts.");
      }

      await fetchInbox();
      setSelected(null);

      const generatedCount = Number(json?.actions_generated || 0);
      const errorDetails =
        Array.isArray(json?.errors) && json.errors.length > 0
          ? ` ${json.errors.join(" | ")}`
          : "";
      const fallbackSuffix = json?.used_fallback ? " Used upcoming payable fallback." : "";
      const scopeLabel = generateAll ? "for all problems" : "for this problem";

      setFeedback(
        generatedCount > 0
          ? `Generated ${generatedCount} AI draft${generatedCount === 1 ? "" : "s"} ${scopeLabel}.${fallbackSuffix}`
          : `No draft was generated.${errorDetails || fallbackSuffix || " No eligible payable was found."}`
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate AI drafts.";
      setFeedback(message);
    } finally {
      setIsGeneratingDrafts(false);
    }
  };

  const selectedEmailFrom = getEmailField(selected?.rawPayload, "email_from");
  const selectedEmailTo = getEmailField(selected?.rawPayload, "email_to");
  const selectedEmailSubject = getEmailField(selected?.rawPayload, "email_subject");
  const selectedEmailBody =
    getEmailField(selected?.rawPayload, "email_body") ||
    getEmailField(selected?.rawPayload, "communication_draft");
  const emailLines = formatEmailBody(selectedEmailBody);
  const isEmailDraft = Boolean(selected?.hasCommunicationDraft && selectedEmailBody);
  const hasDraftableProblems = actions.some((action) => action.canGenerateDrafts && !action.hasCommunicationDraft);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Action Inbox</h1>
          <p className="text-sm text-gray-400 mt-1">AI-generated interventions awaiting your approval</p>
        </div>
        {hasDraftableProblems && (
          <button
            onClick={() => generateDrafts(true)}
            disabled={isGeneratingDrafts}
            className="shrink-0 px-4 py-3 rounded-2xl bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white font-semibold text-sm flex items-center gap-2 transition-colors shadow-sm"
          >
            <Mail size={16} />
            {isGeneratingDrafts ? "Drafting..." : "Draft All Problems"}
          </button>
        )}
      </div>
      <div className="mb-8">
        {feedback && <p className="text-sm text-indigo-600 mt-3">{feedback}</p>}
      </div>

      {/* Inbox list */}
      <div className="flex flex-col gap-3">
        {actions.length === 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <CheckCircle2 size={28} className="text-emerald-400 mx-auto mb-3" />
            <p className="text-sm font-semibold text-gray-600">All clear — no pending actions</p>
          </div>
        )}
        {actions.map((action, i) => {
          const style = priorityStyles[action.priority];
          return (
            <motion.button
              key={action.id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => setSelected(action)}
              className="bg-white rounded-2xl border border-gray-200 shadow-sm px-5 py-4 flex items-center gap-4 text-left hover:border-indigo-200 hover:shadow-md transition-all w-full"
            >
              <span className={`w-2 h-2 rounded-full shrink-0 ${style.dot}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-800">{action.title}</p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">{action.subtitle}</p>
              </div>
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border uppercase tracking-wide shrink-0 ${style.badge}`}>
                {action.priority}
              </span>
              <ChevronRight size={15} className="text-gray-300 shrink-0" />
            </motion.button>
          );
        })}
      </div>

      {/* Full-page modal overlay */}
      <AnimatePresence>
        {selected && (
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 flex items-center justify-center p-6"
            onClick={(e) => { if (e.target === e.currentTarget) setSelected(null); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 20 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
              className="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden"
            >
              {/* Modal header */}
              <div className="flex items-start justify-between px-8 py-6 border-b border-gray-100">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Zap size={14} className="text-indigo-500" />
                    <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest">AI Intervention</span>
                  </div>
                  <h2 className="text-xl font-bold text-gray-900">{selected.title}</h2>
                  <p className="text-sm text-gray-400 mt-0.5">{selected.subtitle}</p>
                </div>
                <button onClick={() => setSelected(null)} className="p-2 rounded-xl hover:bg-gray-100 transition-colors">
                  <X size={18} className="text-gray-400" />
                </button>
              </div>

              {/* Modal body — two columns */}
              <div className="flex-1 overflow-y-auto">
                <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-100 min-h-full">
                  {/* Left: Chain-of-Thought Audit Trail */}
                  <div className="p-8">
                    <div className="flex items-center gap-2 mb-6">
                      <Zap size={14} className="text-indigo-400" />
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Chain-of-Thought</p>
                    </div>
                    {selected.steps.length === 0 ? (
                      <p className="text-xs text-gray-400 italic">No reasoning data recorded for this action.</p>
                    ) : (
                      <div className="flex flex-col gap-0">
                        {selected.steps.map((step: Step, idx: number) => (
                          <motion.div
                            key={idx}
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.1 }}
                            className="flex gap-4"
                          >
                            {/* Stepper line */}
                            <div className="flex flex-col items-center">
                              <div className="w-7 h-7 rounded-full bg-indigo-50 border-2 border-indigo-200 flex items-center justify-center text-indigo-600 text-xs font-bold shrink-0">
                                {idx + 1}
                              </div>
                              {idx < selected.steps.length - 1 && (
                                <div className="w-px flex-1 bg-indigo-100 my-1" />
                              )}
                            </div>
                            {/* Step content */}
                            <div className={`pb-6 ${idx === selected.steps.length - 1 ? "pb-0" : ""}`}>
                              <p className="text-sm font-semibold text-gray-800 mb-0.5">{step.label}</p>
                              <p className="text-xs text-gray-500 leading-relaxed">{step.detail}</p>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Right: Recommended Action */}
                  <div className="p-8">
                    <div className="flex items-center gap-2 mb-6">
                      <FileText size={14} className="text-gray-400" />
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
                        {isEmailDraft ? "Drafted Email" : "Recommended Action"}
                      </p>
                    </div>
                    {isEmailDraft ? (
                      <div className="rounded-[28px] border border-slate-200 bg-white shadow-sm overflow-hidden">
                        <div className="px-6 py-5 border-b border-slate-100 bg-slate-50">
                          <div className="flex items-center gap-2 mb-3">
                            <div className="w-10 h-10 rounded-2xl bg-indigo-100 text-indigo-700 flex items-center justify-center">
                              <Mail size={18} />
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Outbound Email Draft</p>
                              <p className="text-xs text-slate-500">Ready for review before sending</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 gap-3 text-sm">
                            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 mb-1">From</p>
                              <p className="text-slate-700 break-words">{selectedEmailFrom || "CashPilot Finance Team"}</p>
                            </div>
                            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 mb-1">To</p>
                              <p className="text-slate-700 break-words">{selectedEmailTo || "Recipient pending"}</p>
                            </div>
                            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 mb-1">Subject</p>
                              <p className="text-slate-900 font-medium break-words">{selectedEmailSubject || "Subject pending"}</p>
                            </div>
                          </div>
                        </div>
                        <div className="px-6 py-6 bg-white">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 mb-4">Body</p>
                          <div className="rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] px-5 py-5">
                            <div className="space-y-4 text-sm leading-7 text-slate-700 whitespace-pre-wrap">
                              {emailLines.map((line, idx) => (
                                <p key={`${idx}-${line.slice(0, 12)}`} className={line ? "" : "h-4"}>
                                  {line || " "}
                                </p>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : selected.payload.length === 0 ? (
                      <p className="text-xs text-gray-400 italic">No action payload recorded.</p>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {selected.payload.map((item: Step, idx: number) => (
                          <div key={idx} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                            <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">{item.label}</p>
                            <p className="text-xs text-gray-700 leading-relaxed">{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Sticky footer */}
              <div className="px-8 py-5 border-t border-gray-100 bg-white flex gap-4">
                {selected.canGenerateDrafts && !selected.hasCommunicationDraft && (
                  <button
                    onClick={() => generateDrafts(false)}
                    disabled={isGeneratingDrafts}
                    className="flex-1 py-3.5 rounded-2xl bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-300 text-white font-bold text-sm flex items-center justify-center gap-2 transition-colors shadow-sm"
                  >
                    <Mail size={17} />
                    {isGeneratingDrafts ? "Generating..." : "Draft For This Problem"}
                  </button>
                )}
                <button
                  onClick={() => dismiss(selected.id)}
                  className="flex-1 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm flex items-center justify-center gap-2 transition-colors shadow-sm"
                >
                  <CheckCircle2 size={17} />
                  Approve &amp; Execute
                </button>
                <button
                  onClick={() => dismiss(selected.id)}
                  className="flex-1 py-3.5 rounded-2xl bg-red-50 hover:bg-red-100 text-red-600 font-bold text-sm flex items-center justify-center gap-2 transition-colors border border-red-200"
                >
                  <XCircle size={17} />
                  Reject
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

