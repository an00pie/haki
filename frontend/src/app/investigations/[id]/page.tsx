"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ShieldAlert, 
  ArrowLeft, 
  FileText, 
  Download, 
  Trash2, 
  RefreshCw, 
  CheckCircle2, 
  AlertTriangle, 
  Eye, 
  Cpu, 
  Layers, 
  Video, 
  Database, 
  Clock, 
  ExternalLink,
  Upload,
  Sparkles,
  Info,
  Terminal,
  Activity
} from "lucide-react";
import { api } from "@/lib/api";
import { CaseDetailResponse, Finding, ToolAudit, Evidence } from "@/types";

export default function InvestigationWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [data, setData] = useState<CaseDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active tab: 'findings' | 'timeline' | 'evidence' | 'gemma' | 'video'
  const [activeTab, setActiveTab] = useState<string>("findings");

  // Actions state
  const [explaining, setExplaining] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [videoUploading, setVideoUploading] = useState(false);

  const loadCase = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCase(caseId);
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load investigation details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      loadCase();
    }
  }, [caseId]);

  const handleExplain = async () => {
    setExplaining(true);
    try {
      await api.explainCase(caseId);
      await loadCase();
      setActiveTab("gemma");
    } catch (err: any) {
      alert(`Gemma interpretation failed: ${err.message}`);
    } finally {
      setExplaining(false);
    }
  };

  const handleGenerateReport = async () => {
    setGeneratingReport(true);
    try {
      const report = await api.generateReport(caseId);
      window.open(api.getReportDownloadUrl(report.id), "_blank");
      await loadCase();
    } catch (err: any) {
      alert(`Report generation failed: ${err.message}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    const file = e.target.files[0];
    setVideoUploading(true);
    try {
      await api.uploadVideo(caseId, file, data?.case.product_name || data?.case.store_url || "");
      await loadCase();
      setActiveTab("video");
    } catch (err: any) {
      alert(`Video verification failed: ${err.message}`);
    } finally {
      setVideoUploading(false);
    }
  };

  const handleDeleteCase = async () => {
    if (!confirm("Are you sure you want to permanently delete this investigation and its evidence files?")) return;
    try {
      await api.deleteCase(caseId);
      router.push("/dashboard");
    } catch (err: any) {
      alert(`Failed to delete case: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center space-y-4">
        <RefreshCw className="w-6 h-6 text-[#e5ff00] animate-spin mx-auto" />
        <p className="text-xs font-mono text-neutral-400 uppercase tracking-widest">
          [ LOADING WORKSPACE :: CASE {caseId.slice(0, 8)} ]
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="py-16 max-w-lg mx-auto text-center space-y-4 border border-[#242424] bg-[#101010] p-8 rounded-lg">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-white">Investigation Not Found</h2>
        <p className="text-xs font-mono text-neutral-400">{error || "Case record does not exist in local ACID store."}</p>
        <Link
          href="/dashboard"
          className="inline-flex items-center space-x-2 px-4 py-2 rounded bg-neutral-200 text-black text-xs font-mono font-semibold hover:bg-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>RETURN TO DASHBOARD</span>
        </Link>
      </div>
    );
  }

  const { case: c, evidence, findings, audits, risk, stage1, stage2 } = data;
  const score = risk.risk_indicator ?? 0;
  const riskBand = score >= 60 ? "high" : score >= 25 ? "medium" : "low";

  return (
    <div className="space-y-8">
      {/* Back button & Action Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
        <div className="space-y-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center space-x-1.5 text-[11px] font-mono uppercase tracking-wider text-neutral-400 hover:text-[#e5ff00] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>&lt; DASHBOARD</span>
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              {c.title}
            </h1>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase ${
                c.status === "completed"
                  ? "bg-[#e5ff00]/10 text-[#e5ff00] border border-[#e5ff00]/30"
                  : "bg-neutral-800 text-neutral-300 border border-neutral-700"
              }`}
            >
              [{c.status}]
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-neutral-400 font-mono">
            {c.store_url && (
              <a href={c.store_url} target="_blank" rel="noreferrer" className="hover:text-[#e5ff00] inline-flex items-center space-x-1">
                <span>{c.store_url}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {c.seller_handle && <span className="text-neutral-300">@{c.seller_handle}</span>}
            <span className="text-neutral-500">CASE_ID: {c.id.slice(0, 8)}</span>
          </div>
        </div>

        {/* Global Case Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleExplain}
            disabled={explaining}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded bg-[#161616] hover:bg-[#202020] border border-[#333] text-neutral-200 text-xs font-mono transition-colors disabled:opacity-50"
            title="Summarize findings using local Gemma model"
          >
            <Sparkles className={`w-3.5 h-3.5 text-[#e5ff00] ${explaining ? "animate-spin" : ""}`} />
            <span>{explaining ? "GEMMA EXECUTING..." : "EXPLAIN WITH GEMMA"}</span>
          </button>

          <button
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded bg-[#e5ff00] hover:bg-[#d4ec00] text-black text-xs font-mono font-bold transition-colors disabled:opacity-50"
            title="Compile SHA-256 PDF report"
          >
            <FileText className={`w-3.5 h-3.5 ${generatingReport ? "animate-spin" : ""}`} />
            <span>{generatingReport ? "COMPILING PDF..." : "EXPORT PDF REPORT"}</span>
          </button>

          <button
            onClick={handleDeleteCase}
            className="p-1.5 rounded bg-[#161616] hover:bg-red-950/30 border border-[#333] hover:border-red-800 text-neutral-400 hover:text-red-400 transition-colors"
            title="Delete investigation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Two-Stage Risk Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Risk Score Card */}
        <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-neutral-400">
              [ 01 // RISK INDICATOR ]
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                riskBand === "high"
                  ? "bg-red-950/50 text-red-400 border border-red-800/60"
                  : riskBand === "medium"
                  ? "bg-amber-950/50 text-amber-400 border border-amber-800/60"
                  : "bg-neutral-800 text-[#e5ff00] border border-[#e5ff00]/40"
              }`}
            >
              {riskBand} RISK
            </span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className="text-4xl sm:text-5xl font-mono font-bold text-white tracking-tight">{score}</span>
            <span className="text-xs text-neutral-500 font-mono">/ 100</span>
          </div>

          <div className="w-full bg-[#1c1c1c] h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                riskBand === "high"
                  ? "bg-red-500"
                  : riskBand === "medium"
                  ? "bg-amber-400"
                  : "bg-[#e5ff00]"
              }`}
              style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
            />
          </div>

          <div className="text-[11px] text-neutral-400 flex justify-between font-mono pt-1 border-t border-[#1c1c1c]">
            <span>STRENGTH: <span className="text-white uppercase">{risk.evidence_strength || "weak"}</span></span>
            <span>CONFIDENCE: <span className="text-white">{((risk.confidence || 0) * 100).toFixed(0)}%</span></span>
          </div>
        </div>

        {/* Stage 1 Assessment Details */}
        <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] flex flex-col justify-between space-y-3">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-neutral-300" />
            <span className="text-[11px] font-mono uppercase tracking-wider text-neutral-400">
              [ 02 // STAGE 1 DECISION ]
            </span>
          </div>

          <div className="space-y-1">
            <div className="text-sm font-medium text-neutral-200">
              {stage1?.decision?.message || "Preliminary seller assessment completed."}
            </div>
            <p className="text-xs text-neutral-400 font-mono">
              RULES ENGINE: <span className="text-[#e5ff00]">v{stage1?.risk_rules_version || "1.2.0"}</span>
            </p>
          </div>

          <div className="p-2.5 rounded bg-[#161616] border border-[#242424] text-xs font-mono text-neutral-400">
            VERIFICATION THRESHOLD: <span className="text-white font-bold">40 / 100</span>
          </div>
        </div>

        {/* Stage 2 Video Verification Recommendation */}
        <div className="p-5 rounded-lg bg-[#101010] border border-[#242424] flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Video className="w-4 h-4 text-[#e5ff00]" />
              <span className="text-[11px] font-mono uppercase tracking-wider text-neutral-400">
                [ 03 // STAGE 2 VIDEO ]
              </span>
            </div>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${stage2 ? "bg-[#e5ff00]/20 text-[#e5ff00]" : "bg-neutral-800 text-neutral-400"}`}>
              {stage2 ? "VERIFIED" : "OPTIONAL"}
            </span>
          </div>

          {stage2 ? (
            <div className="space-y-2">
              <div className="text-xs text-[#e5ff00] font-mono flex items-center space-x-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>VIDEO FRAMES PARSED LOCALLY</span>
              </div>
              <p className="text-xs text-neutral-400 font-mono">
                {stage2.sampled_frame_count} FRAMES • OCR: {stage2.ocr?.status || "checked"}
              </p>
              <button
                onClick={() => setActiveTab("video")}
                className="text-xs font-mono text-[#e5ff00] hover:underline inline-flex items-center space-x-1"
              >
                <span>INSPECT FRAMES</span>
                <ArrowLeft className="w-3 h-3 rotate-180" />
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-neutral-400">
                Upload demonstration video or seller Reel to perform frame-level analysis and OCR.
              </p>
              <label className="inline-flex items-center space-x-2 px-3 py-1.5 rounded bg-[#161616] hover:bg-[#202020] border border-[#333] text-neutral-200 text-xs font-mono font-medium cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5 text-[#e5ff00]" />
                <span>{videoUploading ? "ANALYZING..." : "UPLOAD PRODUCT VIDEO"}</span>
                <input
                  type="file"
                  accept="video/mp4,video/quicktime"
                  onChange={handleVideoUpload}
                  disabled={videoUploading}
                  className="hidden"
                />
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Workspace Tabs Navigation */}
      <div className="border-b border-[#242424] flex items-center space-x-1 overflow-x-auto">
        {[
          { key: "findings", label: `[01 // FINDINGS (${findings.length})]`, icon: Layers },
          { key: "timeline", label: `[02 // EXECUTION TRACE (${audits.length})]`, icon: Cpu },
          { key: "evidence", label: `[03 // EVIDENCE LEDGER (${evidence.length})]`, icon: Database },
          { key: "gemma", label: "[04 // GEMMA OBSERVATIONS]", icon: Sparkles },
          { key: "video", label: "[05 // VIDEO VERIFICATION]", icon: Video },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center space-x-2 px-4 py-3 text-xs font-mono transition-colors whitespace-nowrap border-b-2 ${
                isActive
                  ? "border-[#e5ff00] text-[#e5ff00] bg-[#141414]"
                  : "border-transparent text-neutral-400 hover:text-white"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Findings Matrix */}
      {activeTab === "findings" && (
        <div className="space-y-4">
          <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden">
            <div className="p-4 border-b border-[#242424] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Corroborated & Observed Risk Findings
              </h3>
              <span className="text-[11px] text-neutral-500 font-mono">
                Deterministic Engine v1.2.0 • Weight &gt; 0 requires corroboration
              </span>
            </div>

            {findings.length === 0 ? (
              <div className="p-8 text-center text-neutral-500 font-mono text-xs">
                [ NO RISK FINDINGS RECORDED ]
              </div>
            ) : (
              <div className="divide-y divide-[#1f1f1f]">
                {findings.map((f) => (
                  <div key={f.id} className="p-5 hover:bg-[#141414] transition-colors space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-bold text-[#e5ff00]">
                          [{f.category}]
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase ${
                            f.status === "corroborated"
                              ? "bg-red-950/40 text-red-400 border border-red-800/40"
                              : f.status === "observed"
                              ? "bg-neutral-800 text-neutral-300 border border-neutral-700"
                              : "bg-neutral-900 text-neutral-500"
                          }`}
                        >
                          {f.status}
                        </span>
                      </div>

                      <div className="flex items-center space-x-4 text-xs font-mono">
                        <span className="text-neutral-400">
                          WEIGHT: <strong className={f.risk_weight > 0 ? "text-red-400" : "text-neutral-400"}>+{f.risk_weight}</strong>
                        </span>
                        <span className="text-neutral-500">
                          CONFIDENCE: {((f.confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    <p className="text-sm text-neutral-200">{f.claim}</p>

                    {f.source_url && (
                      <div className="text-[11px] text-neutral-500 font-mono truncate">
                        SOURCE: <a href={f.source_url} target="_blank" rel="noreferrer" className="text-neutral-400 hover:text-[#e5ff00] underline">{f.source_url}</a>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Execution Trace / Tool Audits */}
      {activeTab === "timeline" && (
        <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden">
          <div className="p-4 border-b border-[#242424]">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
              LangGraph Step Execution & Tool Audits
            </h3>
            <p className="text-xs text-neutral-400 font-mono mt-1">
              Forensically logged steps, inputs, and responses.
            </p>
          </div>

          <div className="divide-y divide-[#1f1f1f]">
            {audits.map((a, i) => (
              <div key={a.id || i} className="p-5 hover:bg-[#141414] transition-colors space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-5 h-5 rounded bg-[#1c1c1c] text-[#e5ff00] text-[10px] font-mono flex items-center justify-center font-bold">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-bold text-xs text-white font-mono">{a.tool_name}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        a.status === "completed"
                          ? "bg-neutral-800 text-[#e5ff00]"
                          : a.status === "unavailable"
                          ? "bg-amber-950/40 text-amber-400"
                          : "bg-neutral-900 text-neutral-500"
                      }`}
                    >
                      {a.status}
                    </span>
                  </div>
                  <span className="text-[11px] text-neutral-500 font-mono">
                    {new Date(a.created_at).toLocaleTimeString()}
                  </span>
                </div>

                <div className="text-xs text-neutral-400 font-mono bg-[#0a0a0a] p-3 rounded border border-[#202020] space-y-1">
                  <div className="text-neutral-500 truncate">INPUT: {a.input_summary}</div>
                  <div className="text-neutral-300">RESULT: {a.result_summary}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Evidence Explorer */}
      {activeTab === "evidence" && (
        <div className="space-y-4">
          <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden">
            <div className="p-4 border-b border-[#242424] flex items-center justify-between">
              <div>
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                  Immutable Evidence Ledger
                </h3>
                <p className="text-xs text-neutral-400 font-mono mt-1">
                  Locally stored evidence records, SHA-256 digests, and raw payload extractions.
                </p>
              </div>
              <span className="text-xs text-neutral-400 font-mono">{evidence.length} ARTIFACT(S)</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-neutral-300 font-mono">
                <thead className="bg-[#141414] uppercase text-neutral-500 border-b border-[#242424] text-[11px]">
                  <tr>
                    <th className="px-5 py-3">Artifact / File</th>
                    <th className="px-5 py-3">Kind</th>
                    <th className="px-5 py-3">SHA-256 Digest</th>
                    <th className="px-5 py-3">Captured</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1f1f1f]">
                  {evidence.map((ev) => (
                    <tr key={ev.id} className="hover:bg-[#141414] transition-colors">
                      <td className="px-5 py-3 font-medium text-white">{ev.filename}</td>
                      <td className="px-5 py-3 uppercase text-[#e5ff00]">{ev.kind}</td>
                      <td className="px-5 py-3 text-neutral-400 truncate max-w-xs">{ev.sha256}</td>
                      <td className="px-5 py-3 text-neutral-500">
                        {new Date(ev.ingested_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-right space-x-2">
                        <a
                          href={api.getEvidenceContentUrl(caseId, ev.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-[#1c1c1c] hover:bg-[#252525] border border-[#333] text-neutral-200"
                        >
                          <Eye className="w-3 h-3 text-[#e5ff00]" />
                          <span>RAW</span>
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Local Gemma Summary */}
      {activeTab === "gemma" && (
        <div className="rounded-lg bg-[#101010] border border-[#242424] p-6 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#242424] pb-4">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-[#e5ff00]" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Local Gemma AI Findings Summary
              </h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neutral-900 text-neutral-400 font-mono border border-neutral-700">
              ZERO RISK CONTRIBUTION (UNVERIFIED)
            </span>
          </div>

          <div className="p-4 rounded bg-[#161616] border border-[#242424] text-xs text-neutral-400 flex items-start space-x-3">
            <Info className="w-4 h-4 text-[#e5ff00] shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              Gemma analyzes verified evidence stored in the case database and highlights patterns, discrepancies, and suggested next checks. Gemma output is unverified commentary and never assigns risk points.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-3">
              <h4 className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#e5ff00]">Observations</h4>
              <ul className="space-y-2 text-xs text-neutral-300 list-disc list-inside">
                {(findings.filter((f) => f.category === "model_interpretation")?.[0]?.claim || "No specific patterns observed yet. Click 'Explain with Gemma' above to run inference.")
                  .split(" | ")
                  .map((obs, idx) => (
                    <li key={idx} className="leading-relaxed">{obs}</li>
                  ))}
              </ul>
            </div>

            <div className="space-y-3">
              <h4 className="text-[11px] font-mono font-bold uppercase tracking-wider text-amber-400">Uncertainties</h4>
              <p className="text-xs text-neutral-400 leading-relaxed">
                RDAP domain registration records and external reviews cannot be fully verified without official registrar records or independent consumer dispute filings.
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="text-[11px] font-mono font-bold uppercase tracking-wider text-neutral-300">Recommended Next Steps</h4>
              <ul className="space-y-2 text-xs text-neutral-300 list-disc list-inside">
                <li>Verify merchant checkout uses standard buyer-protected credit/debit gateways.</li>
                <li>Avoid non-reversible payment methods (gift cards, wire transfers, direct UPI/crypto).</li>
                <li>Cross-reference product photos with manufacturer official catalog.</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Video Verification (Stage 2) */}
      {activeTab === "video" && (
        <div className="rounded-lg bg-[#101010] border border-[#242424] p-6 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#242424] pb-4">
            <div className="flex items-center space-x-2">
              <Video className="w-4 h-4 text-[#e5ff00]" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Stage 2 Video Frame Inspection
              </h3>
            </div>
            {stage2 && (
              <span className="text-xs font-mono text-neutral-400">
                DURATION: {stage2.metadata?.duration_seconds}s • CODEC: {stage2.metadata?.codec}
              </span>
            )}
          </div>

          {!stage2 ? (
            <div className="p-12 text-center space-y-4">
              <Video className="w-8 h-8 text-neutral-600 mx-auto" />
              <p className="text-xs font-mono text-neutral-400">
                [ NO VIDEO ANALYZED :: UPLOAD MP4 OR MOV FILE TO EXTRACT FRAMES ]
              </p>
              <label className="inline-flex items-center space-x-2 px-4 py-2 rounded bg-neutral-200 hover:bg-white text-black font-mono font-semibold text-xs cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>UPLOAD VIDEO NOW</span>
                <input
                  type="file"
                  accept="video/mp4,video/quicktime"
                  onChange={handleVideoUpload}
                  className="hidden"
                />
              </label>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Sampled Frames Grid */}
              <div>
                <h4 className="text-[11px] font-mono font-bold uppercase text-neutral-400 mb-3">
                  Sampled Representative Frames ({stage2.frames?.length || 0})
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {stage2.frames?.map((frame: any, idx: number) => (
                    <div key={idx} className="rounded bg-[#141414] border border-[#242424] overflow-hidden space-y-1">
                      <div className="aspect-video bg-black flex items-center justify-center text-neutral-600 text-xs font-mono">
                        {frame.evidence_id ? (
                          <img
                            src={api.getEvidenceContentUrl(caseId, frame.evidence_id)}
                            alt={`Frame at ${frame.timestamp_seconds}s`}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <span>Frame #{idx + 1}</span>
                        )}
                      </div>
                      <div className="p-2 text-[10px] text-neutral-400 font-mono flex justify-between">
                        <span>{frame.timestamp_seconds}s</span>
                        <span className="truncate max-w-[80px]" title={frame.difference_hash}>
                          dHash: {frame.difference_hash?.slice(0, 8)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* OCR & Gemma Observations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-[#242424]">
                <div className="space-y-2">
                  <h4 className="text-[11px] font-mono font-bold text-neutral-300 uppercase">Tesseract OCR Text Extraction</h4>
                  <div className="p-4 rounded bg-[#0a0a0a] border border-[#242424] text-xs text-neutral-300 font-mono min-h-[80px]">
                    {stage2.ocr?.samples?.map((s: any) => s.text).filter(Boolean).join(" ") || "No legible text extracted from sampled frames."}
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="text-[11px] font-mono font-bold text-neutral-300 uppercase">Visual Authenticity Observations</h4>
                  <div className="p-4 rounded bg-[#0a0a0a] border border-[#242424] text-xs text-neutral-300 min-h-[80px]">
                    {stage2.visual_analysis?.observations?.length ? (
                      <ul className="list-disc list-inside space-y-1">
                        {stage2.visual_analysis.observations.map((obs: string, i: number) => (
                          <li key={i}>{obs}</li>
                        ))}
                      </ul>
                    ) : (
                      "No digital manipulation indicators or synthetic generation patterns detected."
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
