import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "@/lib/api";

describe("Frontend API Client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("handles successful health check", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok", database: "ok", ollama: "available", public_checks_enabled: true }),
    } as any);

    const health = await api.getHealth();
    expect(health.status).toBe("ok");
    expect(health.ollama).toBe("available");
  });

  it("formats ApiError on 422 with structured detail", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({ detail: "Unsafe or invalid store URL: SSRF blocked" }),
    } as any);

    await expect(api.runScan({ store_url: "http://127.0.0.1" })).rejects.toThrow(ApiError);
  });

  it("builds correct download and content URLs", () => {
    expect(api.getReportDownloadUrl("report-xyz")).toBe("/api/v1/reports/report-xyz/download");
    expect(api.getEvidenceContentUrl("case-1", "ev-2")).toBe("/api/v1/cases/case-1/evidence/ev-2/content");
  });
});
