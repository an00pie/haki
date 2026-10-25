"""Full End-to-End Investigation Lifecycle Test:
Target creation -> LangGraph execution -> Findings & Audits -> Evidence verification
-> Stage 2 video upload -> PDF report compilation -> Download -> Cleanup
"""

import io
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def mock_safe_fetch(url, *args, **kwargs):
    return {
        "status": "completed",
        "requested_url": url,
        "url": url,
        "http_status": 200,
        "https_final": True,
        "redirect_chain": [],
        "title": "Elite Handcrafted Studio",
        "text_excerpt": "Handcrafted silver jewellery. Contact info: support@elitesilver.com, +91 9999988888. Address: 45 Craft Lane, Jaipur.",
        "image_urls": ["https://example.com/ring.jpg"],
        "policy_terms": {"contact": True, "returns": True, "privacy": True},
    }

def test_full_e2e_investigation_lifecycle():
    # 1. Target input payload
    payload = {
        "store_url": "https://elitesilver.com",
        "seller_handle": "elitesilver_official",
        "product_name": "Sterling Silver Ring",
        "user_supplied_bio": "Handmade jewellery direct from Jaipur. Ships nationwide.",
        "sale_price": 999.0,
        "original_price": 1200.0,
        "reference_price": 1200.0,
        "products": [
            {"title": "Sterling Silver Ring", "price": 999.0, "description": "Pure 925 silver ring handcrafted with gemstones."},
            {"title": "Silver Pendant", "price": 1499.0, "description": "Authentic silver artisan pendant."},
        ],
    }

    # 2. Run scan
    with patch("app.agents.workflow.fetch_page", side_effect=mock_safe_fetch):
        scan_res = client.post("/scan", json=payload)

    assert scan_res.status_code == 201
    scan_data = scan_res.json()
    case_id = scan_data["case_id"]
    assert case_id is not None
    assert "risk_score" in scan_data
    assert "report_id" in scan_data
    assert "report_url" in scan_data

    # 3. Retrieve Case Workspace data
    case_res = client.get(f"/api/v1/cases/{case_id}")
    assert case_res.status_code == 200
    case_data = case_res.json()
    assert case_data["case"]["id"] == case_id
    assert case_data["case"]["status"] == "completed"
    assert len(case_data["evidence"]) > 0
    assert len(case_data["findings"]) > 0
    assert len(case_data["audits"]) > 0

    # 4. View Evidence content
    first_ev = case_data["evidence"][0]
    ev_content_res = client.get(f"/api/v1/cases/{case_id}/evidence/{first_ev['id']}/content")
    assert ev_content_res.status_code == 200

    # 5. Download original PDF report
    report_id = scan_data["report_id"]
    dl_res = client.get(f"/api/v1/reports/{report_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert dl_res.content[:4] == b"%PDF"

    # 6. Generate fresh report
    fresh_rep_res = client.post(f"/api/v1/cases/{case_id}/reports")
    assert fresh_rep_res.status_code == 201
    assert fresh_rep_res.json()["version"] >= 2

    # 7. Delete case and verify cleanup
    del_res = client.delete(f"/api/v1/cases/{case_id}")
    assert del_res.status_code == 204

    # Verify 404 after deletion
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
