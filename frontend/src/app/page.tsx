"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  ArrowUpRight, 
  Search, 
  Terminal, 
  ShieldAlert, 
  Cpu, 
  Lock, 
  Globe, 
  Instagram, 
  Video, 
  FileCheck 
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const [targetInput, setTargetInput] = useState("");

  const handleQuickScan = (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetInput.trim()) return;

    const trimmed = targetInput.trim();
    if (trimmed.includes("instagram.com") || trimmed.startsWith("@")) {
      const handle = trimmed.replace(/^@/, "").replace(/.*instagram\.com\//, "").split("/")[0].split("?")[0];
      router.push(`/investigations/new?handle=${encodeURIComponent(handle)}`);
    } else {
      router.push(`/investigations/new?url=${encodeURIComponent(trimmed)}`);
    }
  };

  return (
    <div className="space-y-20 py-4 max-w-6xl mx-auto">
      {/* Hero Section */}
      <section className="space-y-6 pt-6 text-center sm:text-left">
        <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-md bg-[#141414] border border-[#2e2e2e] text-[#e5ff00] font-mono text-[11px] tracking-wider uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-[#e5ff00]" />
          <span>[HaKi // v1.2.0 DETERMINISTIC PROTOCOL]</span>
        </div>

        <div className="space-y-3">
          <h1 className="text-4xl sm:text-7xl font-black tracking-tight text-white leading-none">
            Trust is earned. <br />
            <span className="text-neutral-400 font-normal">Evidence is proved.</span>
          </h1>
          <p className="text-sm sm:text-base text-neutral-400 max-w-2xl font-normal leading-relaxed pt-2">
            HaKi evaluates online merchants, storefront domains, and social commerce profiles using strict deterministic risk rules and local Gemma AI. Zero tracking, zero hallucinations.
          </p>
        </div>

        {/* Neo-Minimalist Quick Scan Input */}
        <form onSubmit={handleQuickScan} className="max-w-2xl pt-4">
          <div className="flex flex-col sm:flex-row items-stretch gap-2 p-1.5 rounded-lg bg-[#111111] border border-[#262626] focus-within:border-white transition-all shadow-xl">
            <div className="flex items-center px-3 flex-1 space-x-2">
              <span className="text-neutral-500 font-mono text-xs">$&gt;</span>
              <input
                type="text"
                value={targetInput}
                onChange={(e) => setTargetInput(e.target.value)}
                placeholder="storefront URL (https://...) or Instagram handle (@brand)..."
                className="w-full bg-transparent border-none text-neutral-100 placeholder-neutral-600 py-2.5 text-xs font-mono focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="inline-flex items-center justify-center space-x-2 px-5 py-2.5 rounded-md bg-white hover:bg-neutral-200 text-black font-bold text-xs tracking-wider uppercase transition-transform active:scale-95 shrink-0"
            >
              <span>Scan Target</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex items-center space-x-6 mt-3 text-[11px] text-neutral-500 font-mono">
            <span>[01] SSRF-GUARDED</span>
            <span>[02] 100% LOCAL GEMMA</span>
            <span>[03] AUDITABLE LEDGER</span>
          </div>
        </form>
      </section>

      {/* Neo-Minimal Pillars Grid */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] hover:border-neutral-600 transition-colors space-y-4">
          <div className="flex justify-between items-start text-neutral-500">
            <span className="text-[10px] text-[#e5ff00]">[01 // DOMAIN & STOREFRONT]</span>
            <Globe className="w-4 h-4 text-neutral-400" />
          </div>
          <h3 className="text-sm font-bold text-white font-sans">SSRF-Protected Domain Inspection</h3>
          <p className="text-neutral-400 leading-relaxed font-sans text-xs">
            Inspects DNS records, RDAP registration age, policy consistency, and Wayback machine archives while strictly blocking private, loopback, and cloud metadata targets.
          </p>
        </div>

        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] hover:border-neutral-600 transition-colors space-y-4">
          <div className="flex justify-between items-start text-neutral-500">
            <span className="text-[10px] text-[#e5ff00]">[02 // INSTAGRAM SIGNALS]</span>
            <Instagram className="w-4 h-4 text-neutral-400" />
          </div>
          <h3 className="text-sm font-bold text-white font-sans">Instagram Seller Authenticity</h3>
          <p className="text-neutral-400 leading-relaxed font-sans text-xs">
            Evaluates account tenure, follower-to-following skew, visible comment duplication, and engagement ratios. Supports official Meta Graph API with graceful fallback to manual samples.
          </p>
        </div>

        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] hover:border-neutral-600 transition-colors space-y-4">
          <div className="flex justify-between items-start text-neutral-500">
            <span className="text-[10px] text-[#e5ff00]">[03 // VIDEO VERIFICATION]</span>
            <Video className="w-4 h-4 text-neutral-400" />
          </div>
          <h3 className="text-sm font-bold text-white font-sans">Stage 2 Media Analysis</h3>
          <p className="text-neutral-400 leading-relaxed font-sans text-xs">
            Bounded FFmpeg frame sampling, perceptual difference hashing, Tesseract OCR, and local Gemma visual analysis. Distinguishes seller risk from media observations.
          </p>
        </div>
      </section>

      {/* Architectural Tenets Grid */}
      <section className="p-6 sm:p-8 rounded-lg bg-[#101010] border border-[#242424] space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#242424] pb-6">
          <div>
            <span className="text-[10px] font-mono text-[#e5ff00] uppercase tracking-widest">[PROTOCOL PRINCIPLES]</span>
            <h2 className="text-lg font-bold text-white mt-1">Deterministic Scoring Ownership</h2>
          </div>
          <Link
            href="/dashboard"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-[#181818] hover:bg-[#222222] border border-[#333333] text-xs font-mono text-white transition-colors"
          >
            <span>Open Dashboard</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
          <div className="p-4 rounded-md bg-[#0a0a0a] border border-[#1f1f1f] space-y-2">
            <div className="text-[10px] text-neutral-500">[NODE GRAPH]</div>
            <div className="font-bold text-white font-sans text-sm">LangGraph Engine</div>
            <p className="text-neutral-400 font-sans text-xs">Parallel branches for catalog, domain identity, and complaints with isolated error bounds.</p>
          </div>

          <div className="p-4 rounded-md bg-[#0a0a0a] border border-[#1f1f1f] space-y-2">
            <div className="text-[10px] text-neutral-500">[LOCAL ONLY]</div>
            <div className="font-bold text-white font-sans text-sm">Local Gemma AI</div>
            <p className="text-neutral-400 font-sans text-xs">Zero cloud API tokens. Gemma interprets findings within strict unverified delimiters.</p>
          </div>

          <div className="p-4 rounded-md bg-[#0a0a0a] border border-[#1f1f1f] space-y-2">
            <div className="text-[10px] text-neutral-500">[INDICATOR]</div>
            <div className="font-bold text-white font-sans text-sm">Provisional Scoring</div>
            <p className="text-neutral-400 font-sans text-xs">Risk scores represent observable signals, never definitive fraud accusations.</p>
          </div>

          <div className="p-4 rounded-md bg-[#0a0a0a] border border-[#1f1f1f] space-y-2">
            <div className="text-[10px] text-neutral-500">[DIGEST]</div>
            <div className="font-bold text-white font-sans text-sm">SHA-256 PDF Ledger</div>
            <p className="text-neutral-400 font-sans text-xs">Reports embed cryptographic evidence snapshots and timestamps for complete auditability.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
