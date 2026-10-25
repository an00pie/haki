"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { 
  FileText, 
  Download, 
  ArrowLeft, 
  ShieldCheck, 
  ExternalLink, 
  RefreshCw, 
  AlertTriangle 
} from "lucide-react";
import { api } from "@/lib/api";

export default function ReportViewerPage() {
  const params = useParams();
  const reportId = params.id as string;

  const [loading, setLoading] = useState(false);
  const [reportUrl, setReportUrl] = useState<string>("");

  useEffect(() => {
    if (reportId) {
      setReportUrl(api.getReportDownloadUrl(reportId));
    }
  }, [reportId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
        <div className="space-y-2">
          <Link
            href="/history"
            className="inline-flex items-center space-x-1.5 text-[11px] font-mono uppercase tracking-wider text-neutral-400 hover:text-[#e5ff00] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>&lt; ARCHIVE HISTORY</span>
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <FileText className="w-5 h-5 text-[#e5ff00]" />
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Evidence-Backed PDF Report
            </h1>
            <span className="px-2 py-0.5 rounded bg-[#161616] border border-[#242424] text-neutral-300 text-[11px] font-mono">
              REPORT_ID: {reportId.slice(0, 8)}
            </span>
          </div>
          <p className="text-xs text-neutral-400 font-mono">
            Formally compiled PDF document embedding findings, tool audits, stage 1 risk score, and SHA-256 evidence snapshot hashes.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <a
            href={reportUrl}
            download
            className="inline-flex items-center space-x-2 px-4 py-2 rounded bg-[#e5ff00] hover:bg-[#d4ec00] text-black font-mono font-bold text-xs transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>DOWNLOAD PDF FILE</span>
          </a>
        </div>
      </div>

      {/* Embedded PDF Viewer */}
      <div className="rounded-lg bg-[#101010] border border-[#242424] overflow-hidden p-2">
        <div className="aspect-[4/3] sm:aspect-[16/10] w-full bg-[#0a0a0a] rounded overflow-hidden border border-[#1f1f1f]">
          <iframe
            src={reportUrl}
            title={`Report ${reportId}`}
            className="w-full h-full border-none"
          />
        </div>
      </div>

      {/* Forensic Verification Notice */}
      <div className="p-4 rounded-lg bg-[#121212] border border-[#242424] text-xs text-neutral-400 font-mono flex items-start space-x-3">
        <ShieldCheck className="w-4 h-4 text-[#e5ff00] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-white block uppercase tracking-wider text-[11px]">
            [ FORENSIC INTEGRITY VERIFICATION ]
          </span>
          <p className="leading-relaxed">
            This PDF report is generated with an immutable cryptographic digest calculated over all corroborated evidence records, tool execution logs, and deterministic risk parameters. Any post-generation tampering invalidates the verification digest.
          </p>
        </div>
      </div>
    </div>
  );
}
