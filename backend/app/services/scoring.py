"""Deterministic multi-factor risk scoring engine for ScamTrace AI.

Separates:
1. Risk Score (0-100, provisional heuristic indicator)
2. Confidence (0.0-1.0, certainty based on evidence corroboration and known data)
3. Coverage (0.0-1.0, proportion of applicable checks completed vs unavailable/unattempted)

Correlated rules are grouped with explicit group caps to prevent double-counting.
Ad tracking parameters contribute 0 risk points.
"""

from typing import Any, Sequence
from collections import defaultdict
from app.schemas.findings import FindingModel

SCORING_VERSION = "2.0.0"

# PROVISIONAL / UN-CALIBRATED: Rule severity weight mappings
SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 30,
    "high": 20,
    "medium": 12,
    "low": 6,
    "info": 0,
}

# Rule to Group mapping
RULE_TO_GROUP: dict[str, str] = {
    # Domain & Identity
    "lookalike_domain": "domain_identity",
    "brand_domain_mismatch": "domain_identity",
    "domain_age": "domain_identity",
    "rdap_domain_registration": "domain_identity",
    "linked_domain": "domain_identity",

    # Storefront Policies & Contact
    "policy_conflicts": "storefront_policies",
    "false_business_information": "storefront_policies",
    "payment_identity_mismatch": "storefront_policies",

    # Catalog & Pricing
    "catalog_incoherence": "catalog_pricing",
    "duplicate_descriptions": "catalog_pricing",
    "implausible_discount": "catalog_pricing",
    "uniform_pricing": "catalog_pricing",

    # Social & Instagram Consistency
    "instagram_claims_vs_website": "social_consistency",
    "instagram_account_maturity": "social_consistency",
    "instagram_follower_credibility": "social_consistency",
    "instagram_website_link": "social_consistency",
    "account_maturity_anomaly": "social_consistency",
    "follower_credibility_anomaly": "social_consistency",
    "bio_website_anomaly": "social_consistency",
    "engagement_anomaly": "social_consistency",
    "profile_business_inconsistency": "social_consistency",

    # Public Complaints
    "public_complaints": "public_reputation",
    "public_complaint_leads": "public_reputation",

    # Ad Tracking (Strictly 0 risk points)
    "ad_tracking_params": "ad_tracking",
}

# PROVISIONAL / UN-CALIBRATED: Group caps to prevent double-counting
GROUP_CAPS: dict[str, int] = {
    "domain_identity": 35,
    "storefront_policies": 25,
    "catalog_pricing": 25,
    "social_consistency": 30,
    "public_reputation": 25,
    "ad_tracking": 0,  # Zero points: tracking parameters are provenance only
}

ALL_CHECK_CATEGORIES = {
    "domain_identity",
    "storefront_policies",
    "catalog_pricing",
    "social_consistency",
    "public_reputation",
}

def score_investigation(
    findings: Sequence[Any],
    audits: Sequence[Any] = (),
) -> dict[str, Any]:
    """Compute deterministic risk, confidence, and coverage metrics from findings.

    Handles both Pydantic FindingModel instances and SQLAlchemy Finding models.
    """
    group_points = defaultdict(int)
    group_contributions = defaultdict(list)
    positive_count = 0
    negative_count = 0
    unknown_count = 0
    total_checks = 0

    evaluated_rules = set()

    for f in findings:
        # Extract fields from either FindingModel or ORM Finding
        if isinstance(f, FindingModel):
            rule_id = f.rule_id
            outcome = f.outcome
            severity = f.severity
            finding_id = f.rule_id
            rationale = f.rationale
            risk_weight = f.metadata.get("risk_weight") if f.metadata else None
        else:
            # SQLAlchemy model or dict
            rule_id = getattr(f, "category", "") or getattr(f, "rule_id", "")
            status = getattr(f, "status", "unverified")
            if status in {"corroborated", "observed"} and getattr(f, "risk_weight", 0) > 0:
                outcome = "positive"
            elif status == "corroborated" and getattr(f, "risk_weight", 0) == 0:
                outcome = "negative"
            elif status == "inconclusive":
                outcome = "unknown"
            else:
                outcome = getattr(f, "outcome", "unknown")
            severity = getattr(f, "severity", "low")
            finding_id = getattr(f, "id", rule_id)
            rationale = getattr(f, "claim", "")
            risk_weight = getattr(f, "risk_weight", None)

        group = RULE_TO_GROUP.get(rule_id, "other")
        total_checks += 1
        evaluated_rules.add(rule_id)

        if outcome == "positive":
            positive_count += 1
            if group == "ad_tracking":
                base_weight = 0
            elif risk_weight is not None and risk_weight > 0:
                base_weight = int(risk_weight)
            else:
                base_weight = SEVERITY_WEIGHTS.get(severity, 10)

            group_points[group] += base_weight
            group_contributions[group].append({
                "rule_id": rule_id,
                "finding_id": finding_id,
                "severity": severity,
                "points_added": base_weight,
                "rationale": rationale,
            })
        elif outcome == "negative":
            negative_count += 1
        else:
            unknown_count += 1

    # Apply group caps
    factors = []
    total_risk = 0
    for group, raw_pts in group_points.items():
        cap = GROUP_CAPS.get(group, 25)
        effective_pts = min(cap, raw_pts)
        total_risk += effective_pts
        factors.append({
            "group": group,
            "raw_points": raw_pts,
            "capped_points": effective_pts,
            "group_cap": cap,
            "rules": group_contributions[group],
        })

    final_risk_score = min(100, max(0, total_risk))

    # Risk band categorization
    if final_risk_score >= 70:
        risk_band = "high"
    elif final_risk_score >= 50:
        risk_band = "elevated"
    elif final_risk_score >= 25:
        risk_band = "moderate"
    else:
        risk_band = "low"

    # Coverage computation
    completed_audits = sum(1 for a in audits if getattr(a, "status", None) == "completed")
    unavailable_audits = sum(1 for a in audits if getattr(a, "status", None) == "unavailable")
    unattempted_audits = sum(1 for a in audits if getattr(a, "status", None) == "not_requested")

    # Combine finding coverage
    non_unknown_checks = positive_count + negative_count
    if total_checks > 0:
        coverage_score = round(non_unknown_checks / total_checks, 2)
    else:
        coverage_score = 0.0

    # Confidence computation
    # High confidence requires both non-unknown checks and presence of corroborating evidence
    if total_checks == 0:
        confidence_score = 0.0
    else:
        ratio = non_unknown_checks / total_checks
        if positive_count >= 3 or (negative_count >= 3 and positive_count == 0):
            confidence_score = round(min(1.0, ratio * 0.9 + 0.1), 2)
        elif positive_count >= 1 or negative_count >= 1:
            confidence_score = round(ratio * 0.75, 2)
        else:
            confidence_score = round(ratio * 0.5, 2)

    return {
        "scoring_version": SCORING_VERSION,
        "risk_score": final_risk_score,
        "risk_band": risk_band,
        "confidence": confidence_score,
        "coverage": {
            "score": coverage_score,
            "completed_checks": non_unknown_checks,
            "unknown_checks": unknown_count,
            "total_checks": total_checks,
            "audit_breakdown": {
                "completed": completed_audits,
                "unavailable": unavailable_audits,
                "unattempted": unattempted_audits,
            },
        },
        "factors": sorted(factors, key=lambda x: x["capped_points"], reverse=True),
        "label": "Provisional indicator (not a probability)",
    }
