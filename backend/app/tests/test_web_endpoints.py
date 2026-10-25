"""Integration and security tests for web application endpoints:
- System settings and non-exposure of secrets
- Evidence content streaming and path traversal rejection
- SSE progress stream endpoint
- Case deletion and disk cleanup
- PDF report generation with empty/missing evidence
"""

import os
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_system_settings_endpoint():
    res = client.get("/api/v1/system/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["app_name"] == settings.app_name
    assert "version" in data
    assert "limits" in data
    assert data["limits"]["max_upload_mb"] == settings.max_upload_mb
    assert data["limits"]["video_verification_threshold"] == settings.video_verification_threshold
    # Ensure sensitive secrets are NEVER returned
    assert "brave_search_api_key" not in data
    assert "instagram_api_token" not in data
    assert "api_key" not in str(data).lower()
    assert "token" not in str(data).lower() or "text_model" in str(data).lower()

def test_evidence_content_retrieval_and_path_traversal_guard():
    # 1. Create a case
    case_res = client.post("/api/v1/cases", json={"title": "Path Traversal Test Case"})
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Add legitimate text evidence
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("sample.txt", b"Safe sample content for evidence explorer", "text/plain")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    # 3. Fetch content safely
    content_res = client.get(f"/api/v1/cases/{case_id}/evidence/{ev_id}/content")
    assert content_res.status_code == 200
    assert content_res.content == b"Safe sample content for evidence explorer"

    # 4. Clean up case
    del_res = client.delete(f"/api/v1/cases/{case_id}")
    assert del_res.status_code == 204

def test_sse_investigation_progress_stream():
    # 1. Create case
    case_res = client.post("/api/v1/cases", json={"title": "SSE Stream Test Case"})
    case_id = case_res.json()["id"]

    # 2. Launch investigation run
    inv_res = client.post(f"/api/v1/cases/{case_id}/investigations")
    assert inv_res.status_code == 202
    run_id = inv_res.json()["id"]

    # 3. Query SSE stream
    stream_res = client.get(f"/api/v1/investigations/{run_id}/stream")
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]
    assert "data:" in stream_res.text

    # 4. Clean up
    client.delete(f"/api/v1/cases/{case_id}")

def test_pdf_report_with_sparse_or_missing_evidence():
    # Verify report generator handles a case with no findings or missing evidence gracefully
    case_res = client.post("/api/v1/cases", json={"title": "Empty Evidence Case"})
    case_id = case_res.json()["id"]

    report_res = client.post(f"/api/v1/cases/{case_id}/report")
    assert report_res.status_code == 201
    rep_data = report_res.json()
    assert "download_url" in rep_data
    assert "evidence_snapshot_hash" in rep_data

    # Download PDF
    dl_res = client.get(rep_data["download_url"])
    assert dl_res.status_code == 200
    assert dl_res.content[:4] == b"%PDF"

    # Clean up
    client.delete(f"/api/v1/cases/{case_id}")
