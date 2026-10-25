import { Case, CaseDetailResponse, ScanResult, SystemSettings } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errData: any = null;
    try {
      errData = await res.json();
    } catch {
      errData = await res.text();
    }
    const message = (errData && errData.detail) || res.statusText || `Request failed with ${res.status}`;
    throw new ApiError(res.status, typeof message === "string" ? message : JSON.stringify(message), errData);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export const api = {
  // Health
  getHealth: () => request<{ status: string; database: string; ollama: string; public_checks_enabled: boolean }>("/api/v1/health"),

  // Settings
  getSettings: () => request<SystemSettings>("/api/v1/system/settings"),

  // Cases / Investigations
  getCases: () => request<Case[]>("/api/v1/cases"),
  getCase: (id: string) => request<CaseDetailResponse>(`/api/v1/cases/${id}`),
  deleteCase: (id: string) => request<void>(`/api/v1/cases/${id}`, { method: "DELETE" }),

  // Full Scan / Investigation Creation
  runScan: (payload: {
    store_url?: string;
    seller_handle?: string;
    product_name?: string;
    instagram_url?: string;
    user_supplied_bio?: string;
    sale_price?: number;
    original_price?: number;
    reference_price?: number;
  }) =>
    request<ScanResult>("/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // Video Verification
  uploadVideo: async (caseId: string, file: File, referenceText: string = "") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("reference_text", referenceText);

    return request<{
      case_id: string;
      video_evidence_id: string;
      analysis_evidence_id: string;
      stage2: any;
      final_risk: any;
      message: string;
    }>(`/api/v1/cases/${caseId}/video/verify`, {
      method: "POST",
      body: formData,
    });
  },

  deleteVideo: (caseId: string) =>
    request<{ deleted_evidence_count: number }>(`/api/v1/cases/${caseId}/video`, {
      method: "DELETE",
    }),

  // Evidence
  deleteEvidence: (caseId: string, evidenceId: string) =>
    request<void>(`/api/v1/cases/${caseId}/evidence/${evidenceId}`, {
      method: "DELETE",
    }),

  getEvidenceContentUrl: (caseId: string, evidenceId: string) =>
    `/api/v1/cases/${caseId}/evidence/${evidenceId}/content`,

  // Explain with Gemma
  explainCase: (caseId: string) =>
    request<{
      status: string;
      model: string;
      observations: string[];
      uncertainties: string[];
      next_checks: string[];
    }>(`/api/v1/cases/${caseId}/explain`, {
      method: "POST",
    }),

  // Reports
  generateReport: (caseId: string) =>
    request<{
      id: string;
      case_id: string;
      version: number;
      generated_at: string;
      risk_level: string;
      evidence_snapshot_hash: string;
      download_url: string;
    }>(`/api/v1/cases/${caseId}/reports`, {
      method: "POST",
    }),

  getReportDownloadUrl: (reportId: string) => `/api/v1/reports/${reportId}/download`,
};
