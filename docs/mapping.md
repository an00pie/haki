# ScamTrace AI - Architecture & Feature Mapping

*Date: 25 October 2026*
*Baseline Test Suite: 41 passed (pytest), 9 passed (vitest)*

## Overview
This document records the repository discovery mapping for ScamTrace AI (haki), detailing which files and modules own each feature across the backend and Chrome MV3 extension.

---

## 1. Component Ownership Matrix

| Feature / Responsibility | Existing File Path | Status & Notes |
| :--- | :--- | :--- |
| **FastAPI Entrypoint & CORS** | `backend/app/main.py` | Binds to `127.0.0.1:8000`, applies CORS for local extension. |
| **API Route Handlers** | `backend/app/api/routes.py` | Handles `/inspect`, `/instagram/inspect`, `/cases/{id}/investigations`, `/cases/{id}/video/verify`, `/cases/{id}/product-image/verify`, `/cases/{id}/explain`, `/cases/{id}/report`. |
| **Database Models** | `backend/app/models/entities.py` | SQLAlchemy: `Case`, `Evidence`, `Finding`, `Report`, `ToolAudit`, `InvestigationRun`, `InspectionRequest`. |
| **Database Session & Connection** | `backend/app/database.py` | SQLite connection (`sqlite:///./data/haki.db`), session maker. |
| **Configuration & Environment** | `backend/app/config.py` | Pydantic BaseSettings with strict validation (loopback Ollama, bounded thresholds, timeouts). |
| **Pydantic API Schemas** | `backend/app/schemas/inspect.py`, `cases.py` | Schemas for page inspection, Instagram profile & post snapshots, investigation options, patch payloads. |
| **SSRF-Safe Fetcher & URL Guard** | `backend/app/security/url_guard.py` | `validate_public_url`, `validate_redirect`, `validate_url_for_storage`. Blocks loopback, private, multicast, and metadata IPs (169.254.169.254). |
| **File & Upload Validation** | `backend/app/security/file_validation.py` | `detect_type`, `validate_upload`. Magic byte verification, size limits, and image dimension bounds. |
| **Deterministic Risk Engine** | `backend/app/services/risk_engine.py` | Pure deterministic scoring (`assess()`), signal family deduplication, observed categories, confidence & evidence strength. Version: `1.2.0`. |
| **Instagram Heuristics & Metrics** | `backend/app/services/instagram_assessment.py` | Account maturity, follower-to-following credibility, bio storefront links, engagement repetition, site-profile identity comparison. |
| **Media Discovery & Relevance** | `backend/app/services/media_discovery.py` | Token-based relevance ranking, demonstration/usage prioritization, permitted stream retrieval, bounded candidate evaluation. |
| **Local LLM Explanation (Gemma)** | `backend/app/services/ollama.py` | Ollama client with constrained JSON schema output (`Explanation`), prompt injection sanitization, multimodal vision analysis (`describe_video_frames`). |
| **Report Generation (PDF)** | `backend/app/services/report_builder.py` | ReportLab PDF generator incorporating findings, audits, Stage 1 assessment, Stage 2 video assessment, and discovered media disclosures. |
| **Video Processing & OCR** | `backend/app/tools/video_analysis.py` | FFmpeg frame extraction, duration/codec validation via ffprobe, perceptual hash deduplication, Tesseract OCR integration. |
| **Image Analysis (dHash)** | `backend/app/tools/image_analysis.py` | Deterministic 64-bit difference hash (`difference_hash`) and Hamming distance calculation. |
| **Safe Web Fetching Tool** | `backend/app/tools/web_fetch.py` | Safe HTTP page fetcher, policy keyword detection, text excerpt bounding. |
| **Chrome MV3 Content Scripts** | `extension/src/content/page-inspector.ts`, `instagram-inspector.ts` | User-triggered active DOM extraction (products, prices, Instagram profile/posts/reels). No background crawling or cookies. |
| **Extension Popup UI** | `extension/src/popup/InstagramAssessment.tsx`, `App.tsx`, `ProductPhotoUpload.tsx`, `VideoUpload.tsx` | React 19 UI with two-stage risk visualization, threshold alerts, media verification tabs, and local Gemma summarizer. |

---

## 2. Orchestration Analysis
- **Current State**: Sequential pipeline inside `backend/app/api/routes.py` (`investigate()` function) with execution budget (`steps_used` capped at `settings.max_tool_executions`) recording each step in `ToolAudit`.
- **Target Architecture (Phase 3)**: LangGraph state graph with parallel branches:
  `validate -> profile -> inspect_site -> [catalog_pricing | domain_identity | complaints] -> dedupe -> score -> explain -> report`
- `langgraph` (v1.2.17) and `langchain-core` (v1.7.0) are already available in the Python virtual environment.
- Empty module `backend/app/agents/` exists and can house the modular LangGraph orchestrator.

---

## 3. Test Baseline Record
Recorded on **25 October 2026**:
- **Backend (Pytest)**: `41 passed, 1 warning in 3.42s`
  - `test_extension_api.py` (6 tests): PASSED
  - `test_image_analysis.py` (1 test): PASSED
  - `test_instagram_assessment.py` (6 tests): PASSED
  - `test_media_discovery.py` (8 tests): PASSED
  - `test_ollama.py` (4 tests): PASSED
  - `test_risk_engine.py` (3 tests): PASSED
  - `test_url_guard.py` (6 tests): PASSED
  - `test_video_workflow.py` (7 tests): PASSED
- **Extension (Vitest & TSC)**: `9 passed (9)`, TypeScript 0 errors, Vite build successful.
