"use client";

import React, { useEffect, useState } from "react";
import { 
  Settings, 
  ShieldCheck, 
  Database, 
  Cpu, 
  Lock, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  KeyRound, 
  SlidersHorizontal 
} from "lucide-react";
import { api } from "@/lib/api";
import { SystemSettings } from "@/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsRes, healthRes] = await Promise.all([
        api.getSettings().catch(() => null),
        api.getHealth(),
      ]);
      setSettings(settingsRes);
      setHealth(healthRes);
    } catch (err: any) {
      setError(err.message || "Failed to load system settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
        <div>
          <div className="text-[11px] font-mono text-[#e5ff00] uppercase tracking-wider mb-1">
            [ POLICIES & BOUNDARIES ]
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
            Settings & Security Parameters
          </h1>
          <p className="text-xs text-neutral-400 font-mono mt-1">
            Inspection engine policies, local model endpoints, upload bounds, and privacy controls.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center space-x-2 px-3 py-1.5 rounded bg-[#161616] hover:bg-[#202020] text-neutral-300 text-xs font-mono border border-[#333] transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>CHECK STATUS</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded bg-red-950/40 border border-red-800 text-red-200 text-xs font-mono">
          [ ERROR: {error} ]
        </div>
      )}

      {/* Engine & Database Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
          <div className="flex items-center space-x-2 border-b border-[#242424] pb-3">
            <Database className="w-4 h-4 text-neutral-300" />
            <h2 className="text-[11px] font-mono font-bold text-neutral-400 uppercase tracking-wider">
              [ 01 // LOCAL PERSISTENCE ]
            </h2>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">ENGINE</span>
              <span className="text-white font-semibold">SQLite (Local ACID)</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">STATUS</span>
              <span className="text-[#e5ff00] font-semibold flex items-center space-x-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{health?.database || "CONNECTED"}</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">SERVICE BINDING</span>
              <span className="text-neutral-300">127.0.0.1:8000 (Loopback only)</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-neutral-500">RISK RULES LEDGER</span>
              <span className="text-neutral-300">v1.2.0 (Deterministic)</span>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
          <div className="flex items-center space-x-2 border-b border-[#242424] pb-3">
            <Cpu className="w-4 h-4 text-[#e5ff00]" />
            <h2 className="text-[11px] font-mono font-bold text-neutral-400 uppercase tracking-wider">
              [ 02 // LOCAL LLM INFERENCE ]
            </h2>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">OLLAMA STATUS</span>
              <span className={`font-semibold flex items-center space-x-1 ${health?.ollama === "available" ? "text-[#e5ff00]" : "text-amber-400"}`}>
                <span>{health?.ollama === "available" ? "ONLINE" : "UNAVAILABLE (FALLBACK ACTIVE)"}</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">VISION FRAME MODEL</span>
              <span className="text-neutral-300">{health?.model || "gemma3:4b"}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-[#1c1c1c]">
              <span className="text-neutral-500">TEXT SUMMARY MODEL</span>
              <span className="text-neutral-300">{health?.text_model || "gemma:2b"}</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-neutral-500">INFERENCE BOUNDARY</span>
              <span className="text-[#e5ff00]">100% LOCAL (0 CLOUD TOKENS)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Security & SSRF Policy */}
      <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#242424] pb-3">
          <Lock className="w-4 h-4 text-[#e5ff00]" />
          <h2 className="text-[11px] font-mono font-bold text-neutral-400 uppercase tracking-wider">
            [ 03 // SSRF & EXTERNAL NETWORK PROTECTIONS ]
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="p-3.5 rounded bg-[#141414] border border-[#202020] space-y-1">
            <span className="font-mono text-white text-[11px] font-bold block uppercase tracking-wider">
              Blocked Network Destinations
            </span>
            <p className="text-neutral-400 font-mono text-[11px] leading-relaxed">
              Strictly blocks loopback (127.0.0.0/8), RFC1918 private LANs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), link-local, multicast, and cloud metadata (169.254.169.254).
            </p>
          </div>

          <div className="p-3.5 rounded bg-[#141414] border border-[#202020] space-y-1">
            <span className="font-mono text-white text-[11px] font-bold block uppercase tracking-wider">
              Redirect Re-validation
            </span>
            <p className="text-neutral-400 font-mono text-[11px] leading-relaxed">
              Every redirect in an HTTP fetch chain is re-validated through the DNS resolver and IP filter to prevent redirect-based SSRF and DNS rebinding attacks.
            </p>
          </div>
        </div>
      </div>

      {/* Operational Limits */}
      <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#242424] pb-3">
          <SlidersHorizontal className="w-4 h-4 text-neutral-300" />
          <h2 className="text-[11px] font-mono font-bold text-neutral-400 uppercase tracking-wider">
            [ 04 // OPERATIONAL LIMITS & THRESHOLDS ]
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">MAX UPLOAD SIZE</div>
            <div className="text-sm font-bold text-white">25 MB</div>
          </div>
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">MAX VIDEO UPLOAD</div>
            <div className="text-sm font-bold text-white">100 MB</div>
          </div>
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">VIDEO DURATION LIMIT</div>
            <div className="text-sm font-bold text-white">180 SECONDS</div>
          </div>
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">MAX SAMPLED FRAMES</div>
            <div className="text-sm font-bold text-white">12 FRAMES</div>
          </div>
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">TOOL STEP BUDGET</div>
            <div className="text-sm font-bold text-white">8 STEPS</div>
          </div>
          <div className="p-3 rounded bg-[#141414] border border-[#202020]">
            <div className="text-neutral-500 mb-1 text-[10px]">STAGE 2 RECOMMENDATION</div>
            <div className="text-sm font-bold text-[#e5ff00]">40 / 100 POINTS</div>
          </div>
        </div>
      </div>

      {/* Integration Credentials Status */}
      <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#242424] pb-3">
          <KeyRound className="w-4 h-4 text-neutral-300" />
          <h2 className="text-[11px] font-mono font-bold text-neutral-400 uppercase tracking-wider">
            [ 05 // OPTIONAL INTEGRATION SECRETS ]
          </h2>
        </div>

        <p className="text-xs text-neutral-400 font-mono">
          Access tokens are kept strictly on the backend. No secret values are ever exposed to the client bundle.
        </p>

        <div className="space-y-3 text-xs font-mono">
          <div className="flex justify-between items-center py-2 border-b border-[#1c1c1c]">
            <div>
              <span className="text-white font-semibold block">Brave Search API</span>
              <span className="text-neutral-500 text-[11px]">Enables public consumer complaint searching</span>
            </div>
            <span className="text-neutral-400">
              {settings?.features?.brave_search_configured ? "[CONFIGURED]" : "[NOT CONFIGURED]"}
            </span>
          </div>

          <div className="flex justify-between items-center py-2">
            <div>
              <span className="text-white font-semibold block">Instagram Meta Graph API</span>
              <span className="text-neutral-500 text-[11px]">Enables official account metadata and business profile ingestion</span>
            </div>
            <span className="text-neutral-400">
              {settings?.features?.meta_graph_api_configured ? "[CONFIGURED]" : "[NOT CONFIGURED]"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
