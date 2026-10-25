"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  History, 
  Search, 
  Filter, 
  Trash2, 
  ExternalLink, 
  RefreshCw, 
  FileText, 
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  FolderOpen
} from "lucide-react";
import { api } from "@/lib/api";
import { Case } from "@/types";

export default function HistoryPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCases();
      setCases(data);
    } catch (err: any) {
      setError(err.message || "Failed to load investigations");
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
    if (!confirm("Are you sure you want to permanently delete this investigation?")) return;
    try {
      await api.deleteCase(id);
      setCases((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
    }
  };

  // Filtered and Paginated
  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.store_url && c.store_url.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.seller_handle && c.seller_handle.toLowerCase().includes(searchQuery.toLowerCase())) ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.ceil(filteredCases.length / itemsPerPage) || 1;
  const paginatedCases = filteredCases.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
        <div>
          <div className="text-[11px] font-mono text-[#e5ff00] uppercase tracking-wider mb-1">
            [ ARCHIVE :: AUDIT TRAILS ]
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
            Investigation Archive & History
          </h1>
          <p className="text-xs text-neutral-400 font-mono mt-1">
            Search, filter, inspect immutable records, and reopen prior investigation workspaces.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="p-2 rounded bg-[#161616] hover:bg-[#202020] text-neutral-300 border border-[#333] transition-colors"
          title="Refresh history"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Search and Filters Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#101010] p-3 rounded-lg border border-[#242424]">
        <div className="relative w-full sm:w-96">
          <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search by store URL, handle, title, or ID..."
            className="w-full pl-9 pr-3 py-1.5 rounded bg-[#0a0a0a] border border-[#242424] text-neutral-200 text-xs focus:outline-none focus:border-[#e5ff00] font-mono placeholder:text-neutral-600"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-3.5 h-3.5 text-neutral-500" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-1.5 rounded bg-[#0a0a0a] border border-[#242424] text-neutral-300 text-xs focus:outline-none focus:border-[#e5ff00] font-mono"
          >
            <option value="all">STATUS: ALL</option>
            <option value="completed">STATUS: COMPLETED</option>
            <option value="investigating">STATUS: INVESTIGATING</option>
            <option value="created">STATUS: CREATED</option>
          </select>
        </div>
      </div>

      {/* Cases Table */}
      <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden">
        {loading ? (
          <div className="p-16 text-center text-neutral-500 text-xs font-mono space-y-2">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-[#e5ff00]" />
            <span>[ RETRIEVING HISTORICAL ARCHIVES ]</span>
          </div>
        ) : paginatedCases.length === 0 ? (
          <div className="p-16 text-center text-neutral-500 text-xs font-mono space-y-3">
            <History className="w-6 h-6 text-neutral-600 mx-auto" />
            <p>[ NO INVESTIGATION RECORDS MATCH FILTER CRITERIA ]</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-neutral-300 font-mono">
              <thead className="bg-[#141414] text-[11px] text-neutral-500 uppercase border-b border-[#242424]">
                <tr>
                  <th className="px-5 py-3 font-semibold">Case Title</th>
                  <th className="px-5 py-3 font-semibold">Target Store / Handle</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Timestamp</th>
                  <th className="px-5 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1f1f1f]">
                {paginatedCases.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-[#141414] transition-colors group cursor-pointer"
                    onClick={() => window.location.href = `/investigations/${c.id}`}
                  >
                    <td className="px-5 py-3.5 font-medium text-white max-w-xs truncate">
                      <span className="group-hover:text-[#e5ff00] transition-colors">
                        {c.title}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-neutral-400 max-w-xs truncate text-[11px]">
                      {c.store_url || (c.seller_handle ? `@${c.seller_handle}` : "-")}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          c.status === "completed"
                            ? "bg-[#e5ff00]/10 text-[#e5ff00] border border-[#e5ff00]/30"
                            : c.status === "investigating"
                            ? "bg-neutral-800 text-neutral-300 border border-neutral-700"
                            : "bg-neutral-900 text-neutral-500"
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-neutral-500 text-[11px]">
                      {new Date(c.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                      <Link
                        href={`/investigations/${c.id}`}
                        className="inline-flex items-center px-2.5 py-1 rounded bg-[#1c1c1c] hover:bg-[#252525] text-neutral-200 border border-[#333] hover:border-neutral-400 text-xs transition-colors"
                      >
                        Open
                      </Link>
                      <button
                        onClick={(e) => handleDelete(c.id, e)}
                        className="p-1 rounded hover:bg-red-950/30 text-neutral-500 hover:text-red-400 transition-colors"
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

        {/* Pagination Controls */}
        <div className="p-3 border-t border-[#242424] flex items-center justify-between text-xs text-neutral-400 font-mono">
          <span>
            SHOWING {paginatedCases.length} OF {filteredCases.length} RECORDS
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="p-1 rounded bg-[#161616] border border-[#333] text-neutral-300 disabled:opacity-30 hover:bg-[#202020]"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="text-white text-xs">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="p-1 rounded bg-[#161616] border border-[#333] text-neutral-300 disabled:opacity-30 hover:bg-[#202020]"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
