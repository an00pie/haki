"""API integration tests for the LangGraph /scan and Stage 2 video endpoints."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def fake_fetch_page(url, *args, **kwargs):
    return {
        "status": "completed",
        "requested_url": url,
        "url": url,
        "http_status": 200,
        "https_final": True,
        "redirect_chain": [],
        "title": "Authentic Organic Store - Handcrafted Goods",
        "text_excerpt": "Welcome to our organic store. We ship handcrafted goods across India. Contact support@organicstore.in or call +91-9876543210 at 12 MG Road, Bangalore.",
        "image_urls": ["https://example.com/item1.jpg"],
        "policy_terms": {"contact": True, "returns": True, "privacy": True},
    }

def test_scan_with_website_and_pasted_bio():
    """Verify /scan endpoint runs LangGraph workflow and returns full structured response."""
    payload = {
        "store_url": "https://organicstore.in",
        "seller_handle": "organic_crafts",
        "product_name": "Herbal Tea Pack",
        "user_supplied_bio": "100% natural herbal teas handpicked from Assam gardens.",
        "sale_price": 499.0,
        "original_price": 599.0,
        "reference_price": 599.0,
        "products": [
            {"title": "Herbal Tea Pack", "price": 499, "description": "Authentic whole leaf Assam tea."},
            {"title": "Green Tea Blend", "price": 399, "description": "Crisp Himalayan green tea leaves."},
            {"title": "Chamomile Infusion", "price": 450, "description": "Relaxing pure chamomile flower tea."},
        ],
    }

    with patch("app.agents.workflow.fetch_page", side_effect=fake_fetch_page):
        response = client.post("/scan", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "case_id" in data
    assert "risk_score" in data
    assert "risk_band" in data
    assert "confidence" in data
    assert "coverage" in data
    assert "reasons" in data
    assert "limitations" in data
    assert "next_steps" in data
    assert "explanation" in data
    assert "report_url" in data
    assert data["risk_band"] in {"low", "moderate", "elevated", "high"}

    # Test downloading the generated report
    report_res = client.get(data["report_url"])
    assert report_res.status_code == 200
    assert report_res.headers["content-type"] == "application/pdf"
    assert report_res.content[:4] == b"%PDF"

def test_scan_with_instagram_url_and_pasted_bio_only():
    """Verify /scan works when only an Instagram URL and pasted bio are provided."""
    payload = {
        "instagram_url": "https://instagram.com/handloom_treasures",
        "seller_handle": "handloom_treasures",
        "user_supplied_bio": "Direct from weavers. DM to order. No website, WhatsApp payments only.",
        "sale_price": 1200.0,
    }

    response = client.post("/scan", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"] is not None
    assert isinstance(data["risk_score"], int)
    assert len(data["findings"]) > 0

def test_scan_rejects_unsafe_store_url():
    """Verify /scan blocks SSRF attempts to private IP ranges."""
    payload = {
        "store_url": "http://169.254.169.254/latest/meta-data",
        "seller_handle": "attacker",
    }
    response = client.post("/scan", json=payload)
    assert response.status_code == 422
    assert "Unsafe or invalid store URL" in response.json()["detail"]
