"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { 
  Globe, 
  Instagram, 
  Tag, 
  Video, 
  Upload, 
  Check, 
  AlertCircle, 
  ArrowUpRight, 
  Cpu, 
  Loader2, 
  FileCheck
} from "lucide-react";
import { api } from "@/lib/api";
import { ScanResult } from "@/types";

function NewInvestigationContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Form State
  const [storeUrl, setStoreUrl] = useState("");
  const [sellerHandle, setSellerHandle] = useState("");
  const [productName, setProductName] = useState("");
  const [userBio, setUserBio] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [originalPrice, setOriginalPrice] = useState("");
  const [referencePrice, setReferencePrice] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);

  // Execution State
  const [submitting, setSubmitting] = useState(false);
  const [progressStep, setProgressStep] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const urlParam = searchParams.get("url");
    const handleParam = searchParams.get("handle");
    if (urlParam) setStoreUrl(urlParam);
    if (handleParam) setSellerHandle(handleParam);
  }, [searchParams]);

  const progressSteps = [
    "Validating target inputs and executing SSRF IP filter",
    "Ingesting seller profile & Meta Graph API / fallback data",
    "Querying storefront HTTP, RDAP domain age & archive records",
    "Running parallel LangGraph branches (pricing, identity, complaints)",
    "Executing HaKi pure deterministic risk scoring v1.2.0",
    "Generating structured observations with local Gemma AI",
    "Compiling cryptographic SHA-256 PDF evidence report",
    "Finalizing workspace",
  ];

  const handleVideoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!["video/mp4", "video/quicktime"].includes(file.type)) {
        alert("Please upload an MP4 or MOV video file.");
        return;
      }
      if (file.size > 100 * 1024 * 1024) {
        alert("Video exceeds the 100 MB limit.");
        return;
      }
      setVideoFile(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!storeUrl.trim() && !sellerHandle.trim()) {
      setError("Please provide either a storefront URL or an Instagram handle/URL.");
      return;
    }

    setError(null);
    setSubmitting(true);
    setProgressStep(0);
    setStatusMessage(progressSteps[0]);

    const interval = setInterval(() => {
      setProgressStep((prev) => {
        if (prev < progressSteps.length - 2) {
          const next = prev + 1;
          setStatusMessage(progressSteps[next]);
          return next;
        }
        return prev;
      });
    }, 1400);

    try {
      const payload: any = {
        store_url: storeUrl.trim() || undefined,
        seller_handle: sellerHandle.trim().replace(/^@/, "") || undefined,
        product_name: productName.trim() || undefined,
        user_supplied_bio: userBio.trim() || undefined,
        sale_price: salePrice ? parseFloat(salePrice) : undefined,
        original_price: originalPrice ? parseFloat(originalPrice) : undefined,
        reference_price: referencePrice ? parseFloat(referencePrice) : undefined,
      };

      const result: ScanResult = await api.runScan(payload);

      if (videoFile && result.case_id) {
        setStatusMessage("Uploading and verifying Stage 2 product video via FFmpeg & Gemma...");
        await api.uploadVideo(result.case_id, videoFile, productName || storeUrl);
      }

      clearInterval(interval);
      setProgressStep(progressSteps.length - 1);
      setStatusMessage("Scan complete. Loading workspace...");

      setTimeout(() => {
        router.push(`/investigations/${result.case_id}`);
      }, 600);
    } catch (err: any) {
      clearInterval(interval);
      setSubmitting(false);
      setError(err.message || "Investigation failed. Check inputs and local backend status.");
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 font-sans">
      {/* Header */}
      <div className="border-b border-[#242424] pb-6">
        <span className="text-[10px] font-mono text-[#e5ff00] uppercase tracking-widest">[HaKi // SCAN]</span>
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight mt-0.5">
          Initiate Target Investigation
        </h1>
        <p className="text-xs text-neutral-400 mt-1 font-mono">
          Specify storefront, merchant handle, or pricing claims for deterministic evaluation.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-md bg-[#1a0f0f] border border-rose-900/60 text-rose-300 text-xs font-mono flex items-start space-x-3">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-bold uppercase tracking-wider block">Scan Initiation Failed</span>
            <span className="text-[11px] text-rose-400">{error}</span>
          </div>
        </div>
      )}

      {/* Progress Modal Overlay */}
      {submitting && (
        <div className="fixed inset-0 z-50 bg-[#080808]/95 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-md w-full p-6 rounded-lg bg-[#111111] border border-[#2e2e2e] shadow-2xl space-y-5 font-mono">
            <div className="flex items-center space-x-3 border-b border-[#242424] pb-4">
              <Loader2 className="w-5 h-5 text-[#e5ff00] animate-spin" />
              <div>
                <h3 className="font-bold text-white text-xs uppercase tracking-wider">Executing LangGraph Pipeline</h3>
                <p className="text-[10px] text-neutral-500">Autonomous node execution in progress</p>
              </div>
            </div>

            <div className="p-3 rounded bg-[#0a0a0a] border border-[#202020] text-xs text-[#e5ff00] flex items-center space-x-2">
              <span className="text-neutral-500">&gt;</span>
              <span className="truncate">{statusMessage}</span>
            </div>

            <div className="space-y-2 text-xs">
              {progressSteps.map((step, idx) => (
                <div key={idx} className="flex items-center space-x-2">
                  {idx < progressStep ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  ) : idx === progressStep ? (
                    <div className="w-3.5 h-3.5 rounded-full border border-[#e5ff00] border-t-transparent animate-spin shrink-0" />
                  ) : (
                    <div className="w-3.5 h-3.5 rounded-full bg-[#202020] shrink-0" />
                  )}
                  <span className={idx <= progressStep ? "text-neutral-200 font-sans" : "text-neutral-600 font-sans"}>
                    {step}
                  </span>
                </div>
              ))}
            </div>

            <p className="text-[10px] text-neutral-500 text-center uppercase tracking-widest pt-2">
              [DO NOT NAVIGATE AWAY // LOCAL INFERENCE ACTIVE]
            </p>
          </div>
        </div>
      )}

      {/* Main Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Target Details Card */}
        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
          <div className="flex items-center justify-between border-b border-[#242424] pb-3">
            <span className="text-[10px] font-mono text-[#e5ff00] uppercase tracking-widest">[01 // TARGET IDENTIFIERS]</span>
            <Globe className="w-4 h-4 text-neutral-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-mono text-neutral-300 mb-1.5 uppercase tracking-wider">
                Storefront Website URL
              </label>
              <input
                type="url"
                value={storeUrl}
                onChange={(e) => setStoreUrl(e.target.value)}
                placeholder="https://exclusive-shoes-store.com"
                className="w-full px-3.5 py-2.5 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white font-mono transition-colors"
              />
              <span className="text-[10px] font-mono text-neutral-500 mt-1 block">
                SSRF Guard: Resolves DNS and blocks private LANs and cloud metadata (169.254.169.254).
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-mono text-neutral-300 mb-1.5 uppercase tracking-wider">
                  Instagram Handle or Profile URL
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-neutral-500 text-xs font-mono">
                    @
                  </span>
                  <input
                    type="text"
                    value={sellerHandle}
                    onChange={(e) => setSellerHandle(e.target.value)}
                    placeholder="official_seller"
                    className="w-full pl-8 pr-3.5 py-2.5 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white font-mono transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-neutral-300 mb-1.5 uppercase tracking-wider">
                  Product Name (Optional)
                </label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g. Wireless Pro Earbuds"
                  className="w-full px-3.5 py-2.5 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-mono text-neutral-300 mb-1.5 uppercase tracking-wider">
                Seller Bio or Disclosed Description (Optional)
              </label>
              <textarea
                value={userBio}
                onChange={(e) => setUserBio(e.target.value)}
                rows={2}
                placeholder="Paste seller's bio, terms, or policy snippet (e.g. 'No returns, DM to buy, ships worldwide')..."
                className="w-full px-3.5 py-2 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white transition-colors font-mono"
              />
            </div>
          </div>
        </div>

        {/* Pricing Checks Card */}
        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
          <div className="flex items-center justify-between border-b border-[#242424] pb-3">
            <span className="text-[10px] font-mono text-[#e5ff00] uppercase tracking-widest">[02 // PRICING HEURISTICS]</span>
            <Tag className="w-4 h-4 text-neutral-500" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono">
            <div>
              <label className="block text-[11px] text-neutral-400 mb-1.5 uppercase tracking-wider">
                Listed Sale Price
              </label>
              <input
                type="number"
                step="0.01"
                value={salePrice}
                onChange={(e) => setSalePrice(e.target.value)}
                placeholder="499"
                className="w-full px-3 py-2 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white"
              />
            </div>

            <div>
              <label className="block text-[11px] text-neutral-400 mb-1.5 uppercase tracking-wider">
                Claimed Original Price
              </label>
              <input
                type="number"
                step="0.01"
                value={originalPrice}
                onChange={(e) => setOriginalPrice(e.target.value)}
                placeholder="4999"
                className="w-full px-3 py-2 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white"
              />
            </div>

            <div>
              <label className="block text-[11px] text-neutral-400 mb-1.5 uppercase tracking-wider">
                Market Reference Price
              </label>
              <input
                type="number"
                step="0.01"
                value={referencePrice}
                onChange={(e) => setReferencePrice(e.target.value)}
                placeholder="5500"
                className="w-full px-3 py-2 rounded-md bg-[#0a0a0a] border border-[#262626] text-neutral-200 text-xs focus:border-white"
              />
            </div>
          </div>
          <span className="text-[10px] font-mono text-neutral-500 block">
            Used by rule <code>implausible_discount</code>: discounts &gt; 80% with artificial price markups trigger risk penalties.
          </span>
        </div>

        {/* Optional Stage 2 Video Upload */}
        <div className="p-6 rounded-lg bg-[#101010] border border-[#242424] space-y-4">
          <div className="flex items-center justify-between border-b border-[#242424] pb-3 font-mono">
            <span className="text-[10px] text-[#e5ff00] uppercase tracking-widest">[03 // STAGE 2 VIDEO VERIFICATION]</span>
            <span className="text-[10px] text-neutral-500 uppercase tracking-widest">OPTIONAL</span>
          </div>

          <p className="text-xs text-neutral-400 leading-relaxed font-sans">
            Upload an unboxing, product showcase video, or Instagram Reel. FFmpeg will sample frames, compute difference hashes, run local OCR, and request local Gemma observations.
          </p>

          <div className="border border-dashed border-[#333333] hover:border-neutral-500 rounded-lg p-6 text-center transition-colors bg-[#0a0a0a]">
            {videoFile ? (
              <div className="space-y-2 font-mono">
                <FileCheck className="w-6 h-6 text-[#e5ff00] mx-auto" />
                <div className="text-xs font-bold text-white">{videoFile.name}</div>
                <div className="text-[10px] text-neutral-500">
                  {(videoFile.size / (1024 * 1024)).toFixed(2)} MB • {videoFile.type}
                </div>
                <button
                  type="button"
                  onClick={() => setVideoFile(null)}
                  className="text-[11px] text-rose-400 hover:underline pt-2 block mx-auto uppercase tracking-wider"
                >
                  Remove Video
                </button>
              </div>
            ) : (
              <div className="space-y-2 font-mono">
                <Upload className="w-6 h-6 text-neutral-500 mx-auto" />
                <div className="text-xs text-neutral-300">
                  Drag and drop MP4 / MOV, or{" "}
                  <label className="text-white hover:underline cursor-pointer font-bold">
                    browse file
                    <input
                      type="file"
                      accept="video/mp4,video/quicktime"
                      onChange={handleVideoSelect}
                      className="hidden"
                    />
                  </label>
                </div>
                <div className="text-[10px] text-neutral-500">
                  Max 100 MB • Max 180 seconds • Up to 12 sampled frames
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2 font-mono">
          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center space-x-2 py-3 rounded-md bg-white hover:bg-neutral-200 text-black font-extrabold text-xs tracking-wider uppercase transition-transform active:scale-98 shadow-md"
          >
            <span>Execute Forensic Investigation</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

export default function NewInvestigationPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-xs text-neutral-500 font-mono">loading investigation form...</div>}>
      <NewInvestigationContent />
    </Suspense>
  );
}
