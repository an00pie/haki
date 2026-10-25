# HaKi

HaKi is a local-first, forensic web application and Chrome extension for autonomous seller, online storefront, and social commerce risk intelligence.

It combines an auditable **deterministic risk engine (v1.2.0)**, a **LangGraph state machine**, **SSRF-safe web and domain inspections**, **Instagram Meta Graph API signals with manual/DOM fallbacks**, **bounded FFmpeg/OCR Stage 2 video analysis**, and **100% local Gemma AI inference** with cryptographically hashed PDF reporting.

---

## Architecture Overview

```
                          ┌────────────────────────┐
                          │     HaKi Web App       │  (Next.js 14, React, Tailwind CSS)
                          │   http://localhost:3000│
                          └───────────┬────────────┘
                                      │
                                      │ REST / SSE
                                      ▼
┌─────────────────────────┐      ┌────────────────────────┐
│  Chrome MV3 Extension   ├─────►│  FastAPI Local Backend │  (127.0.0.1:8000)
│  (Isolated Click-to-DOM)│ CORS │  - SSRF URL Guard      │
└─────────────────────────┘      │  - LangGraph Machine   │
                                 │  - Deterministic Scorer│
                                 │  - Meta Graph Adapter  │
                                 │  - FFmpeg Video Sampler│
                                 └───────────┬────────────┘
                                             │
                       ┌─────────────────────┼─────────────────────┐
                       ▼                     ▼                     ▼
              ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
              │ SQLite Database │   │ Local Evidence  │   │ Local Ollama    │
              │  (data/haki.db) │   │ (data/evidence) │   │ (Gemma 3 / 2B)  │
              └─────────────────┘   └─────────────────┘   └─────────────────┘
```

### Component Breakdown
* **Web Frontend** (`frontend/`): Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide icons.
  * `/`: High-impact landing page and rapid target scan launch.
  * `/dashboard`: Operational metrics, scan status, and recent investigations table.
  * `/investigations/new`: Target intake (storefront URL, Instagram handle, pricing anchors, complaint options, and Stage 2 video upload) with live LangGraph execution modal.
  * `/investigations/[id]`: Interactive investigation workspace with 5 forensic tabs (Findings Matrix, Execution Trace Timeline, Evidence Explorer, Local Gemma AI Summary, and Stage 2 Video Verification).
  * `/history`: Historical archive with search, status filtering, pagination, and deletion controls.
  * `/reports/[id]`: Embedded PDF viewer and direct download for cryptographically verified reports.
  * `/settings`: Inspection engine policies, SSRF destination rules, operational thresholds, and system health status.
* **FastAPI Backend** (`backend/app/`):
  * **LangGraph Orchestrator** (`agents/workflow.py`): Parallel state machine (`validate -> profile -> inspect_site -> [catalog_pricing | domain_identity | complaints] -> dedupe -> score -> explain -> report`).
  * **Deterministic Risk Engine** (`services/risk_engine.py`): Pure mathematical rule scoring separating risk score, confidence, and coverage. Requires corroborated evidence before adding risk weight.
  * **Instagram Meta Graph API Adapter** (`services/instagram_graph.py`): Backend-isolated adapter for official business accounts with graceful fallback to user-supplied bios and visible-page extraction.
  * **Video Verification Tool** (`tools/video_analysis.py`): Bounded FFmpeg frame extraction, perceptual difference hash deduplication (dHash), and Tesseract OCR.
  * **Local AI Explanation** (`services/ollama.py` & `explain.py`): Untrusted prompt delimiter sanitization and structured output using local Gemma models (zero cloud tokens).
  * **PDF Report Builder** (`services/report_builder.py`): ReportLab PDF generation embedding timestamps, audits, and a SHA-256 evidence snapshot digest.
* **Chrome MV3 Extension** (`extension/`):
  * Preserved as an independent, fully functioning project.
  * User-triggered DOM extraction (`activeTab`, `scripting`) for live Amazon and Instagram browsing.

---

## Local Setup & Quickstart

### Prerequisites
* Python 3.11+
* Node.js 20+
* FFmpeg and ffprobe (for video analysis)
* Tesseract OCR (optional, for local video text extraction)
* Ollama (optional, for local Gemma AI inference)

### 1. Environment Setup
```bash
# Clone and setup Python virtual environment and dependencies
./scripts/setup.sh

# Copy environment configuration
cp .env.example .env
```

### 2. Start the Backend API
```bash
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
API documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Start the Web Application
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. (Optional) Build & Load the Chrome Extension
```bash
cd extension
npm install
npm run build
```
In Chrome, navigate to `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select `extension/dist`.

### 5. (Optional) Setup Local Gemma Models
```bash
ollama pull gemma3:4b
ollama pull gemma:2b
```
Ollama stays strictly on `127.0.0.1:11434`. If Ollama is unavailable, the deterministic rules, LangGraph execution, and PDF reporting continue to work seamlessly.

---

## Running Verification Tests

### 1. Backend Test Suite (Pytest)
```bash
PYTHONPATH=backend .venv/bin/pytest backend/app/tests
```
Runs 130 tests covering:
* Pure deterministic risk engine and rule weights
* LangGraph state graph parallel branching and cancellation
* Meta / Instagram Graph API failures, expired tokens, and fallbacks
* SSRF guards, private IP blocking, and DNS rebinding protections
* Evidence storage, path traversal defenses, and cascade deletions
* Video duration, resolution bounds, and FFmpeg/OCR frame sampling
* Cryptographic PDF report generation and missing evidence resilience
* End-to-end investigation lifecycle

### 2. Frontend Test Suite (Vitest)
```bash
cd frontend
npm test
npm run build
```
Tests component loading, empty, success, and error states, along with production route prerendering.

### 3. Extension Test Suite (Vitest & TypeScript)
```bash
cd extension
npm test
npm run typecheck
npm run build
```

---

## Docker Deployment

To launch the full production stack using Docker Compose:

```bash
docker compose up --build -d
```
* Web Application: [http://localhost:3000](http://localhost:3000)
* Backend API: [http://localhost:8000](http://localhost:8000)

---

## Security & Privacy Principles

1. **SSRF Guard**: Resolves DNS before requests and validates every redirect hop. Blocks loopback (`127.0.0.0/8`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), multicast, link-local, and cloud metadata (`169.254.169.254`).
2. **Path Traversal Defense**: All evidence and report file requests are resolved and verified against the canonical root of `./data`. Any attempt to access outside directories is rejected with HTTP 403.
3. **No Secret Leaks**: Backend credentials (`BRAVE_SEARCH_API_KEY`, `INSTAGRAM_API_TOKEN`) remain exclusively on the server and are never serialized into responses, logs, or frontend bundles.
4. **Deterministic Sovereignty**: Gemma summaries are classified as unverified commentary with zero risk weight points. Missing data never raises the risk indicator.
5. **No Network Tracking**: All telemetry is local. No user browsing history or payment data is collected or shared.
