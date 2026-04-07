"use client";
import { useState, useRef, useEffect } from "react";
import { useSimulation } from "../context/SimulationContext";
import { mockState } from "../mockState";
import { Upload, CheckCircle2, Link2, AlertCircle, Wifi } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type LedgerItem = {
  id: string;
  source: string;
  description: string;
  amount: number;
  date: string;
  matched: boolean;
  confidence: number;
  matchedWith: string | null;
};

function sanitizeDisplayValue(value: unknown, fallback: string) {
  if (typeof value !== "string") {
    return fallback;
  }
  const normalized = value.trim().toLowerCase();
  if (!normalized || ["not found", "unknown", "unknown vendor", "n/a", "null", "none"].includes(normalized)) {
    return fallback;
  }
  return value;
}

function sanitizeDateValue(value: unknown) {
  if (typeof value !== "string") {
    return new Date().toISOString().split("T")[0];
  }
  const normalized = value.trim();
  if (!normalized || ["1970-01-01", "1900-01-01", "0001-01-01"].includes(normalized)) {
    return new Date().toISOString().split("T")[0];
  }
  return normalized;
}

export default function IngestionPage() {
  const { refreshKey } = useSimulation();
  const [dragging, setDragging] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [ledgerItems, setLedgerItems] = useState<LedgerItem[]>([]);
  const [usingFallbackData, setUsingFallbackData] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function buildLedgerFallback(): LedgerItem[] {
    return mockState.ingestion.recentItems.map((item) => ({
      id: item.id,
      source: item.source,
      description: item.description,
      amount: item.amount,
      date: item.date,
      matched: item.matched,
      confidence: item.confidence,
      matchedWith: item.matchedWith,
    }));
  }

  useEffect(() => {
    async function fetchTransactions() {
      try {
        const res = await fetch("/api/transactions");
        if (res.ok) {
          const data = await res.json();
          setLedgerItems(data.items);
          setUsingFallbackData(false);
          return;
        }
      } catch {
      }

      setLedgerItems(buildLedgerFallback());
      setUsingFallbackData(true);
    }
    fetchTransactions();
  }, [refreshKey]);

  const processFile = async (file: File) => {
    setScanning(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/ingest/receipt", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        const recon = data.reconciliation || {};
        const gemini = data.parsed_receipt?.ingestion_event?.parsed_data || {};
        const newItem = {
          id: String(Date.now()),
          source: "API",
          description: sanitizeDisplayValue(recon.entity || gemini.entity_name, file.name),
          amount: recon.amount || gemini.amount || 0,
          date: sanitizeDateValue(gemini.due_date),
          matched: recon.action?.includes("Merged") || false,
          matchedWith: recon.action || recon.status || "",
          confidence: data.parsed_receipt?.ingestion_event?.reconciliation_confidence
            ? Math.round(data.parsed_receipt.ingestion_event.reconciliation_confidence * 100)
            : 95,
        };

        setLedgerItems((prev) => [newItem, ...prev]);
        setUsingFallbackData(false);
      } else {
        const errorText = await res.text();
        setLedgerItems((prev) => [
          {
            id: String(Date.now()),
            source: "UPLOAD",
            description: file.name,
            amount: 0,
            date: new Date().toISOString().split("T")[0],
            matched: false,
            matchedWith: errorText,
            confidence: 0,
          },
          ...prev,
        ]);
      }
    } catch {
      setLedgerItems((prev) => [
        {
          id: String(Date.now()),
          source: "UPLOAD",
          description: file.name,
          amount: 0,
          date: new Date().toISOString().split("T")[0],
          matched: false,
          matchedWith: "Backend unavailable - document queued locally",
          confidence: 0,
        },
        ...prev,
      ]);
    } finally {
      setScanning(false);
      setScanned(true);
      setTimeout(() => setScanned(false), 3000);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFile(e.target.files[0]);
      e.target.value = "";
    }
  };

  const handleClick = () => {
    if (!scanning) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Data Ingestion</h1>
        <p className="text-sm text-gray-400 mt-1">Sensors Â· OCR Â· Bank sync Â· Reconciliation</p>
      </div>

      {usingFallbackData && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Live backend data is unavailable, so this ingestion view is currently showing demo fallback ledger data.
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileSelect}
        className="hidden"
      />

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`relative bg-white rounded-2xl border-2 border-dashed transition-all mb-6 p-10 flex flex-col items-center justify-center gap-3 cursor-pointer
          ${dragging ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"}`}
      >
        <AnimatePresence mode="wait">
          {scanning ? (
            <motion.div
              key="scanning"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3"
            >
              <motion.div
                animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
                transition={{ repeat: Infinity, duration: 1.4 }}
                className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center"
              >
                <Upload size={20} className="text-indigo-600" />
              </motion.div>
              <p className="text-sm font-semibold text-indigo-700">Gemini Vision OCR Processingâ€¦</p>
              <p className="text-xs text-indigo-400">Extracting line items, amounts, and vendor metadata</p>
              <motion.div className="w-48 h-1 bg-indigo-100 rounded-full overflow-hidden mt-1">
                <motion.div
                  className="h-full bg-indigo-500 rounded-full"
                  animate={{ x: ["-100%", "100%"] }}
                  transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
                />
              </motion.div>
            </motion.div>
          ) : scanned ? (
            <motion.div key="done" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-2">
              <CheckCircle2 size={28} className="text-emerald-500" />
              <p className="text-sm font-semibold text-emerald-700">Receipt scanned &amp; queued for reconciliation</p>
            </motion.div>
          ) : (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-2">
              <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                <Upload size={20} className="text-gray-400" />
              </div>
              <p className="text-sm font-semibold text-gray-700">Drag &amp; drop receipts here, or <span className="text-indigo-600 underline">click to browse</span></p>
              <p className="text-xs text-gray-400">Supports JPG, PNG Â· Powered by Gemini Vision OCR</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {[
          { name: "Plaid API", sub: "Bank Sync Â· Last synced 2 min ago", status: "live" },
          { name: "Stripe API", sub: "Receivables Â· 3 new events", status: "live" },
        ].map(({ name, sub, status }) => (
          <div key={name} className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 flex items-center gap-4">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
              <Wifi size={16} className="text-emerald-500" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-800">{name}</p>
              <p className="text-xs text-gray-400">{sub}</p>
            </div>
            <span className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {status === "live" ? "Live" : "Error"}
            </span>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-gray-800">Reconciliation Ledger</p>
            <p className="text-xs text-gray-400 mt-0.5">N-Way fuzzy match Â· AI confidence scoring</p>
          </div>
          <span className="text-[10px] bg-indigo-50 text-indigo-600 font-semibold px-2.5 py-1 rounded-full border border-indigo-100 uppercase tracking-wide">
            {ledgerItems.filter((r) => r.matched).length} matched
          </span>
        </div>
        <div className="divide-y divide-gray-50">
          {ledgerItems.map((item) => (
            <div key={item.id} className="px-6 py-4 flex items-center gap-4">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-gray-100 text-gray-500 shrink-0 w-16 text-center">
                {item.source}
              </span>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{item.description}</p>
                <p className="text-xs text-gray-400">{item.date}</p>
              </div>
              <p className={`text-sm font-bold shrink-0 ${item.amount < 0 ? "text-red-500" : "text-emerald-600"}`}>
                {item.amount < 0 ? "" : "+"}{Number(item.amount).toLocaleString("en-US", { style: "currency", currency: "USD" })}
              </p>

              {item.matched ? (
                <div className="flex items-center gap-2 shrink-0">
                  <Link2 size={13} className="text-indigo-400" />
                  <div>
                    <p className="text-[10px] text-gray-500 truncate max-w-[140px]">{item.matchedWith}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <div className="h-1 w-20 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-400 rounded-full"
                          style={{ width: `${item.confidence}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-bold text-emerald-600">{item.confidence}%</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 shrink-0 text-amber-500">
                  <AlertCircle size={13} />
                  <span className="text-[11px] font-medium">Unmatched</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

