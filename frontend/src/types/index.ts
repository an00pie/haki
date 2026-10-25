export interface Case {
  id: string;
  title: string;
  mode: string;
  status: string;
  store_url: string | null;
  seller_handle: string | null;
  product_name: string | null;
  amount_minor_units: number | null;
  currency: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  id: string;
  case_id: string;
  kind: string;
  filename: string;
  storage_path: string;
  sha256: string;
  source_url: string | null;
  captured_at: string | null;
  ingested_at: string;
  extraction_status: string;
}

export interface Finding {
  id: string;
  case_id: string;
  category: string;
  claim: string;
  status: string; // "corroborated" | "observed" | "unverified" | "inconclusive"
  confidence: number;
  risk_weight: number;
  source_url: string | null;
  evidence_id: string | null;
  evidence_strength: string; // "strong" | "weak"
  created_at: string;
}

export interface ToolAudit {
  id: string;
  case_id: string;
  run_id: string;
  tool_name: string;
  input_summary: string;
  source_url: string | null;
  status: string;
  result_summary: string;
  created_at: string;
}

export interface Report {
  id: string;
  case_id: string;
  version: number;
  storage_path?: string;
  generated_at: string;
  risk_level: string;
  evidence_snapshot_hash: string;
  download_url?: string;
}

export interface InvestigationRun {
  id: string;
  case_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  steps_used: number;
  error_summary: string | null;
}

export interface RiskFactor {
  category: string;
  claim: string;
  weight: number;
  evidence_strength: string;
  source_url?: string;
}

export interface RiskAssessment {
  risk_indicator: number;
  risk_score?: number;
  risk_band: "low" | "medium" | "high" | "critical";
  confidence: number;
  coverage: Record<string, boolean>;
  factors: RiskFactor[] | string[];
  evidence_strength: "strong" | "weak" | "insufficient";
  uncertainties?: string[];
  rules_version?: string;
}

export interface CaseDetailResponse {
  case: Case;
  evidence: Evidence[];
  findings: Finding[];
  runs: InvestigationRun[];
  audits: ToolAudit[];
  risk: RiskAssessment;
  stage1: any;
  stage2: any;
  stage2_photo: any;
  discovered_media: any;
  final_risk: RiskAssessment;
}

export interface ScanResult {
  case_id: string;
  risk_score: number;
  risk_band: "low" | "medium" | "high" | "critical";
  confidence: number;
  coverage: Record<string, boolean>;
  reasons: string[];
  limitations: string[];
  contradictions: string[];
  next_steps: string[];
  stage2_recommended: boolean;
  stage2_threshold: number;
  explanation?: {
    observations: string[];
    uncertainties: string[];
    next_checks: string[];
  };
  findings: Finding[];
  audits: ToolAudit[];
  report_id: string;
  report_url: string;
}

export interface SystemSettings {
  app_name: string;
  version: string;
  database: string;
  ollama: {
    status: string;
    url: string;
    model: string;
    text_model: string;
  };
  limits: {
    max_upload_mb: number;
    max_video_upload_mb: number;
    max_video_duration_seconds: number;
    max_video_frames: number;
    max_tool_executions: number;
    video_verification_threshold: number;
  };
  features: {
    public_checks_enabled: boolean;
    brave_search_configured: boolean;
    meta_graph_api_configured: boolean;
  };
}
