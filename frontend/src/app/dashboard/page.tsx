"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Plus, 
  Trash2, 
  RefreshCw, 
  Search, 
  ArrowUpRight, 
  AlertCircle 
} from "lucide-react";
import { api } from "@/lib/api";
import { Case } from "@/types";

export default function DashboardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCases();
      setCases(data);
    } catch (err: any) {
      setError(err.message || "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Permanently purge this investigation and all associated evidence files?")) {
      return;
    }
    setDeletingId(id);
    try {
      await api.deleteCase(id);
      setCases((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const completedCount = cases.filter((c) => c.status === "completed").length;
  const inProgressCount = cases.filter((c) => c.status === "investigating" || c.status === "created").length;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header and Quick Action */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
        <div>
          <span className="text-[10px] font-mono text-[#e5ff00] uppercase tracking-widest">[HaKi // OPERATIONS]</span>
          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight mt-0.5">
            Security Intelligence Dashboard
          </h1>
          <p className="text-xs text-neutral-400 mt-1 font-mono">
            Active storefront examinations, social commerce audits, and cryptographic evidence ledgers.
          </p>
        </div>
        <div className="flex items-center space-x-2 font-mono text-xs">
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-md bg-[#121212] hover:bg-[#1a1a1a] text-neutral-300 border border-[#2a2a2a] transition-colors"
            title="Refresh investigations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/investigations/new"
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-md bg-white hover:bg-neutral-200 text-black font-bold text-xs tracking-wider uppercase transition-transform active:scale-95"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Investigation</span>
          </Link>
        </div>
      </div>

      {/* KPI Metrics Grid - Neo-Minimalist Style */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono">
        <div className="p-4 rounded-lg bg-[#101010] border border-[#242424] space-y-2">
          <span className="text-[10px] text-neutral-500 uppercase tracking-widest">[TOTAL CASES]</span>
          <div className="text-3xl font-black text-white">{loading ? "-" : cases.length}</div>
          <div className="text-[10px] text-neutral-500">Persisted locally in SQLite</div>
        </div>

        <div className="p-4 rounded-lg bg-[#101010] border border-[#242424] space-y-2">
          <span className="text-[10px] text-neutral-500 uppercase tracking-widest">[COMPLETED REPORTS]</span>
          <div className="text-3xl font-black text-white">{loading ? "-" : completedCount}</div>
          <div className="text-[10px] text-neutral-500">Hashed with SHA-256</div>
        </div>

        <div className="p-4 rounded-lg bg-[#101010] border border-[#242424] space-y-2">
          <span className="text-[10px] text-neutral-500 uppercase tracking-widest">[IN-FLIGHT RUNS]</span>
          <div className="text-3xl font-black text-[#e5ff00]">{loading ? "-" : inProgressCount}</div>
          <div className="text-[10px] text-neutral-500">LangGraph nodes running</div>
        </div>

        <div className="p-4 rounded-lg bg-[#101010] border border-[#242424] space-y-2">
          <span className="text-[10px] text-neutral-500 uppercase tracking-widest">[PROTOCOL SPEC]</span>
          <div className="text-xl font-black text-white pt-1">HaKi v1.2</div>
          <div className="text-[10px] text-neutral-500">Deterministic + Local Gemma</div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-md bg-[#1a0f0f] border border-rose-900/60 text-rose-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadData}
            className="text-[10px] uppercase font-bold text-white hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Recent Investigations Table */}
      <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden">
        <div className="p-4 border-b border-[#242424] flex items-center justify-between font-mono text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-[#e5ff00]">&gt;</span>
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">Recent Investigations</h2>
          </div>
          <Link
            href="/history"
            className="text-neutral-400 hover:text-white transition-colors inline-flex items-center space-x-1 text-[11px]"
          >
            <span>VIEW ALL ARCHIVE</span>
            <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <div className="p-12 text-center space-y-2 font-mono text-xs text-neutral-500">
            <RefreshCw className="w-4 h-4 animate-spin mx-auto text-[#e5ff00]" />
            <p>loading investigation records...</p>
          </div>
        ) : cases.length === 0 ? (
          <div className="p-12 text-center space-y-4 font-mono">
            <div className="w-10 h-10 rounded-md bg-[#141414] border border-[#262626] flex items-center justify-center text-neutral-500 mx-auto">
              <Search className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">No investigations yet</h3>
              <p className="text-[11px] text-neutral-500 mt-1 max-w-sm mx-auto font-sans">
                Launch a scan on a storefront URL or Instagram seller handle to generate your first auditable evidence ledger.
              </p>
            </div>
            <Link
              href="/investigations/new"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-white hover:bg-neutral-200 text-black font-bold text-xs uppercase tracking-wider transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Start First Scan</span>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono text-neutral-300">
              <thead className="bg-[#0c0c0c] text-[10px] text-neutral-500 uppercase tracking-wider border-b border-[#242424]">
                <tr>
                  <th className="px-5 py-3 font-medium">Target / Case Title</th>
                  <th className="px-5 py-3 font-medium">Storefront / Profile</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e1e1e]">
                {cases.slice(0, 10).map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-[#141414] transition-colors group cursor-pointer"
                    onClick={() => window.location.href = `/investigations/${c.id}`}
                  >
                    <td className="px-5 py-3.5 font-sans font-medium text-white max-w-xs truncate">
                      <span className="group-hover:text-[#e5ff00] transition-colors">
                        {c.title}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-neutral-400 max-w-xs truncate text-[11px]">
                      {c.store_url || (c.seller_handle ? `@${c.seller_handle}` : "-")}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] tracking-wider uppercase font-semibold ${
                          c.status === "completed"
                            ? "bg-[#18281a] text-emerald-400 border border-emerald-900/60"
                            : c.status === "investigating"
                            ? "bg-[#252518] text-[#e5ff00] border border-[#4d4d1a]"
                            : "bg-[#181818] text-neutral-400 border border-[#2a2a2a]"
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-[11px] text-neutral-500">
                      {new Date(c.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                      <Link
                        href={`/investigations/${c.id}`}
                        className="inline-flex items-center px-2 py-1 rounded bg-[#1c1c1c] hover:bg-[#252525] text-[11px] font-semibold text-neutral-200 border border-[#333333] transition-colors"
                      >
                        Workspace
                      </Link>
                      <button
                        onClick={(e) => handleDelete(c.id, e)}
                        disabled={deletingId === c.id}
                        className="inline-flex items-center p-1 rounded hover:bg-[#201010] text-neutral-500 hover:text-rose-400 transition-colors"
                        title="Delete investigation"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
