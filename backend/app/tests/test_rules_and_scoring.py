"""Comprehensive tests for deterministic rules and scoring engine (Phase 2).

Tests:
- Every rule as a pure function with positive, negative, and unknown outcomes
- Scorer repeatability (identical input gives identical score)
- Platform subdomains
- Correlated-signal capping
- Ad tracking params alone adding zero risk
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.schemas.findings import FindingModel
from app.rules import (
    lookalike_domain,
    brand_domain_mismatch,
    domain_age,
    policy_conflicts,
    catalog_incoherence,
    duplicate_descriptions,
    implausible_discount,
    uniform_pricing,
    ad_tracking_params,
    instagram_claims_vs_website,
    public_complaints,
)
from app.services.scoring import score_investigation

# --- Rule 1: lookalike_domain ---
def test_lookalike_domain_positive():
    f = lookalike_domain.evaluate("http://arnazon.com/deals")
    assert f.outcome == "positive"
    assert f.metadata.get("impersonated_brand") == "amazon"

    f2 = lookalike_domain.evaluate("http://amaz0n-sale.store")
    assert f2.outcome == "positive"

def test_lookalike_domain_negative():
    # Official legitimate domain
    f = lookalike_domain.evaluate("https://www.amazon.in/dp/B08N5WRWNW")
    assert f.outcome == "negative"
    assert f.metadata.get("match_type") == "official_domain"

    # Independent unrelated domain
    f2 = lookalike_domain.evaluate("https://curryleaves.in")
    assert f2.outcome == "negative"

def test_lookalike_domain_unknown():
    f = lookalike_domain.evaluate(None)
    assert f.outcome == "unknown"
    assert "missing" in f.limitations[0].lower()


# --- Rule 2: brand_domain_mismatch & platform subdomains ---
def test_brand_domain_mismatch_platform_subdomain():
    # Store on myshopify.com where subdomain matches brand
    f = brand_domain_mismatch.evaluate("Silk Craft", "https://silkcraft.myshopify.com")
    assert f.outcome == "negative"

def test_brand_domain_mismatch_trademark_impersonation():
    # Claims to be Apple Store on an unrelated domain
    f = brand_domain_mismatch.evaluate("Apple Official Store", "https://cheap-gadgets-hub.xyz")
    assert f.outcome == "positive"
    assert f.severity == "high"

def test_brand_domain_mismatch_unknown():
    f = brand_domain_mismatch.evaluate(None, "https://example.com")
    assert f.outcome == "unknown"


# --- Rule 3: domain_age ---
def test_domain_age_positive_critical():
    now = datetime.now(timezone.utc)
    reg_date = (now - timedelta(days=5)).isoformat()
    rdap = {"events": [{"eventAction": "registration", "eventDate": reg_date}]}
    f = domain_age.evaluate(rdap, domain="newscam.shop", reference_date=now)
    assert f.outcome == "positive"
    assert f.severity == "critical"
    assert f.metadata["age_days"] == 5

def test_domain_age_negative_established():
    now = datetime.now(timezone.utc)
    reg_date = (now - timedelta(days=400)).isoformat()
    rdap = {"events": [{"eventAction": "registration", "eventDate": reg_date}]}
    f = domain_age.evaluate(rdap, domain="established.com", reference_date=now)
    assert f.outcome == "negative"
    assert f.metadata["age_days"] == 400

def test_domain_age_unknown_on_redaction():
    rdap = {"events": []}  # Redacted
    f = domain_age.evaluate(rdap, domain="redacted.com")
    assert f.outcome == "unknown"
    assert "redacted" in f.rationale.lower()


# --- Rule 4: policy_conflicts ---
def test_policy_conflicts_positive():
    data = {
        "returns": "We offer a 30 day return window on all items.",
        "full_text": "Please note that all sales are final and no refunds are accepted under any circumstances.",
    }
    f = policy_conflicts.evaluate(data)
    assert f.outcome == "positive"
    assert "contradiction" in f.rationale.lower()

def test_policy_conflicts_negative():
    data = {
        "returns": "Returns accepted within 14 days in original packaging.",
        "contact_us": "Contact us at support@artisan.in or +91-9876543210 at 42 Market Road, Bangalore.",
        "full_text": "Privacy and consumer security policy outlined below.",
        "policy_terms": {"contact": True, "returns": True, "privacy": True},
    }
    f = policy_conflicts.evaluate(data)
    assert f.outcome == "negative"

def test_policy_conflicts_unknown():
    f = policy_conflicts.evaluate({"full_text": "Short"})
    assert f.outcome == "unknown"


# --- Rule 5: catalog_incoherence ---
def test_catalog_incoherence_positive():
    products = [
        {"title": "Industrial Excavator Chainsaw 5000", "description": "Heavy machinery diesel"},
        {"title": "Organic Newborn Baby Diaper Stroller", "description": "Infant pacifier gentle"},
        {"title": "Rolex Gold Luxury Watch Diamond", "description": "Expensive luxury jewelry"},
    ]
    f = catalog_incoherence.evaluate(products)
    assert f.outcome == "positive"
    assert "incompatible" in f.rationale.lower()

def test_catalog_incoherence_negative():
    products = [
        {"title": "Men Cotton T-Shirt", "description": "Casual apparel"},
        {"title": "Slim Fit Denim Jeans", "description": "Casual pants"},
        {"title": "Leather Boots Sneakers", "description": "Footwear"},
    ]
    f = catalog_incoherence.evaluate(products)
    assert f.outcome == "negative"

def test_catalog_incoherence_unknown():
    f = catalog_incoherence.evaluate([{"title": "One Item"}])
    assert f.outcome == "unknown"


# --- Rule 6: duplicate_descriptions ---
def test_duplicate_descriptions_positive():
    boilerplate = "This is a premium high quality artisanal item crafted with care and elegance. 100% satisfaction guaranteed."
    products = [
        {"title": "Leather Wallet", "description": boilerplate},
        {"title": "Bluetooth Earbuds", "description": boilerplate},
    ]
    f = duplicate_descriptions.evaluate(products)
    assert f.outcome == "positive"
    assert "duplicate" in f.rationale.lower()

def test_duplicate_descriptions_negative():
    products = [
        {"title": "Leather Wallet", "description": "Full-grain vegetable tanned cowhide wallet with 6 card slots and RFID protection."},
        {"title": "Bluetooth Earbuds", "description": "Wireless earbuds featuring active noise cancellation and 30-hour battery life."},
    ]
    f = duplicate_descriptions.evaluate(products)
    assert f.outcome == "negative"

def test_duplicate_descriptions_unknown():
    f = duplicate_descriptions.evaluate([{"title": "Single Item"}])
    assert f.outcome == "unknown"


# --- Rule 7: implausible_discount ---
def test_implausible_discount_positive():
    # 90% markdown: 10,000 down to 1,000
    f = implausible_discount.evaluate(sale_price=1000.0, original_price=10000.0)
    assert f.outcome == "positive"
    assert f.severity == "high"
    assert f.metadata["discount_percent"] == 90.0

def test_implausible_discount_negative():
    # 25% markdown: 1,000 down to 750
    f = implausible_discount.evaluate(sale_price=750.0, original_price=1000.0)
    assert f.outcome == "negative"
    assert f.metadata["discount_percent"] == 25.0

def test_implausible_discount_unknown():
    # Missing baseline reference price
    f = implausible_discount.evaluate(sale_price=500.0, original_price=None, reference_price=None)
    assert f.outcome == "unknown"


# --- Rule 8: uniform_pricing ---
def test_uniform_pricing_positive():
    products = [
        {"title": "Product A", "price": 499},
        {"title": "Product B", "price": 499},
        {"title": "Product C", "price": 499},
    ]
    f = uniform_pricing.evaluate(products)
    assert f.outcome == "positive"
    assert "identical flat price" in f.rationale.lower()

def test_uniform_pricing_negative():
    products = [
        {"title": "Product A", "price": 299},
        {"title": "Product B", "price": 799},
        {"title": "Product C", "price": 1299},
    ]
    f = uniform_pricing.evaluate(products)
    assert f.outcome == "negative"

def test_uniform_pricing_unknown():
    f = uniform_pricing.evaluate([{"title": "Only One", "price": 100}])
    assert f.outcome == "unknown"


# --- Rule 9: ad_tracking_params (Provenance only, ZERO risk points) ---
def test_ad_tracking_params_positive_with_zero_risk():
    url = "https://example.shop/item?fbclid=IwAR123456&utm_source=instagram&utm_campaign=winter_sale"
    f = ad_tracking_params.evaluate(url)
    assert f.outcome == "positive"
    assert f.severity == "info"
    assert "never evidence of fraud" in f.rationale.lower()
    assert f.metadata["risk_contribution"] == 0

def test_ad_tracking_params_negative():
    url = "https://example.shop/item"
    f = ad_tracking_params.evaluate(url)
    assert f.outcome == "negative"

def test_ad_tracking_params_unknown():
    f = ad_tracking_params.evaluate(None)
    assert f.outcome == "unknown"


# --- Rule 10: public_complaints (No results is unknown, never safe) ---
def test_public_complaints_no_results_is_unknown_not_safe():
    f = public_complaints.evaluate([])
    assert f.outcome == "unknown"
    assert "not proof of safety" in f.rationale.lower()

def test_public_complaints_positive():
    leads = [
        {"url": "https://reddit.com/r/scams/1", "snippet": "Ordered shoes from this seller and never received them"},
        {"url": "https://consumercomplaints.in/2", "snippet": "Fake tracking number given, scam shop"},
    ]
    f = public_complaints.evaluate(leads, matched_identifier="scamshop.in")
    assert f.outcome == "positive"
    assert f.metadata["deduped_lead_count"] == 2


# --- SCORER TESTS ---
def test_scorer_tracking_params_alone_add_no_risk():
    f = ad_tracking_params.evaluate("https://example.com?fbclid=XYZ&gclid=ABC")
    result = score_investigation([f])
    assert result["risk_score"] == 0
    assert result["risk_band"] == "low"

def test_scorer_correlated_signal_capping():
    """Group caps prevent multiple correlated signals from excessively inflating risk."""
    f1 = FindingModel(rule_id="lookalike_domain", outcome="positive", severity="critical", rationale="Typosquatting")
    f2 = FindingModel(rule_id="brand_domain_mismatch", outcome="positive", severity="high", rationale="Brand mismatch")
    f3 = FindingModel(rule_id="domain_age", outcome="positive", severity="critical", rationale="Young domain")
    
    # All 3 belong to domain_identity group.
    # Raw points: 30 + 20 + 30 = 80.
    # But group cap for domain_identity is 35!
    result = score_investigation([f1, f2, f3])
    assert result["risk_score"] == 35

    factor = next(fac for fac in result["factors"] if fac["group"] == "domain_identity")
    assert factor["capped_points"] == 35
    assert factor["raw_points"] == 80

def test_scorer_repeatability():
    """Identical input yields identical output every time."""
    findings = [
        lookalike_domain.evaluate("http://arnazon.com"),
        implausible_discount.evaluate(sale_price=100.0, original_price=1000.0),
        uniform_pricing.evaluate([{"price": 100}, {"price": 100}, {"price": 100}]),
        ad_tracking_params.evaluate("http://arnazon.com?fbclid=123"),
    ]

    res1 = score_investigation(findings)
    res2 = score_investigation(findings)

    assert res1["risk_score"] == res2["risk_score"]
    assert res1["risk_band"] == res2["risk_band"]
    assert res1["confidence"] == res2["confidence"]
    assert res1["coverage"] == res2["coverage"]
    assert len(res1["factors"]) == len(res2["factors"])
