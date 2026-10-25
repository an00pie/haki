import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    getCases: vi.fn(),
    deleteCase: vi.fn(),
  },
}));

describe("DashboardPage Component States", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    // Return pending promise so loading state remains visible
    vi.mocked(api.getCases).mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);
    expect(screen.getByText(/loading investigation records/i)).toBeDefined();
  });

  it("renders empty state when no cases exist", async () => {
    vi.mocked(api.getCases).mockResolvedValue([]);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/no investigations yet/i)).toBeDefined();
      expect(screen.getByText(/start first scan/i)).toBeDefined();
    });
  });

  it("renders success state with investigations table", async () => {
    const mockCases = [
      {
        id: "case-1234-abcd",
        title: "Test Storefront Check",
        mode: "pre_purchase",
        status: "completed",
        store_url: "https://example-shop.com",
        seller_handle: "exampleshop",
        product_name: "Sneakers",
        amount_minor_units: null,
        currency: "INR",
        notes: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];

    vi.mocked(api.getCases).mockResolvedValue(mockCases as any);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Test Storefront Check")).toBeDefined();
      expect(screen.getByText("https://example-shop.com")).toBeDefined();
      expect(screen.getByText("completed")).toBeDefined();
    });
  });

  it("renders error state when API fails", async () => {
    vi.mocked(api.getCases).mockRejectedValue(new Error("Database connection refused"));

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/database connection refused/i)).toBeDefined();
      expect(screen.getByText(/retry/i)).toBeDefined();
    });
  });
});
