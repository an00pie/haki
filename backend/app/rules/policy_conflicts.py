"""Deterministic policy conflicts and disclosure analysis rule.

Analyzes contact info, physical address, return window consistency,
and mandatory commercial policy disclosures.
"""

import re
from typing import Any
from app.schemas.findings import FindingModel

RULE_ID = "policy_conflicts"
RULE_VERSION = "1.0.0"

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
RETURN_DAYS_PATTERN = re.compile(r"(\d{1,3})\s*(?:-|to)?\s*(?:day|days)\b", re.IGNORECASE)
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "mail.com"}

def evaluate(
    policy_data: dict[str, Any] | None,
    source_url: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate storefront policy statements and contact disclosures for internal conflicts."""
    if not policy_data:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No policy or storefront text was provided to assess policy disclosures.",
            rule_version=RULE_VERSION,
            source=source_url,
            limitations=["Policy data unattempted or missing"],
        )

    # Gather available text segments
    about_text = str(policy_data.get("about_us") or policy_data.get("about") or "")
    contact_text = str(policy_data.get("contact_us") or policy_data.get("contact") or "")
    returns_text = str(policy_data.get("returns") or policy_data.get("refund_policy") or "")
    shipping_text = str(policy_data.get("shipping") or "")
    full_text = str(policy_data.get("full_text") or policy_data.get("text_excerpt") or "")
    combined = f"{about_text} {contact_text} {returns_text} {shipping_text} {full_text}".lower()

    if len(combined.strip()) < 50:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="Storefront text is too sparse to evaluate policy disclosures or terms.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Insufficient page text for policy extraction"],
        )

    conflicts = []

    # 1. Return Window Contradiction Check
    # E.g. Claims "30 day return" but also states "all sales final" or "no refunds"
    has_no_refunds = bool(re.search(r"\b(all sales (are )?final|no refunds?( under any circumstances)?|no returns? accepted)\b", combined))
    return_matches = RETURN_DAYS_PATTERN.findall(returns_text or combined)
    return_days = [int(m) for m in return_matches if 1 <= int(m) <= 365]

    if has_no_refunds and return_days:
        conflicts.append(f"Returns policy specifies a {return_days[0]}-day return window, yet text also states all sales are final/non-refundable.")

    # If multiple contradictory return windows are specified (e.g. 14 days and 90 days in separate sections)
    unique_return_days = sorted(set(return_days))
    if len(unique_return_days) >= 2 and max(unique_return_days) - min(unique_return_days) >= 14:
        conflicts.append(f"Contradictory return periods found: mentions both {min(unique_return_days)} days and {max(unique_return_days)} days.")

    # 2. Contact Information Analysis
    emails = EMAIL_PATTERN.findall(combined)
    free_emails = [e for e in emails if e.split("@")[-1].lower() in FREE_EMAIL_DOMAINS]

    has_physical_address = bool(re.search(r"\b(suite|ste|road|rd|street|st|avenue|ave|p\.?o\.?\s*box|boulevard|blvd|pin\s*code|zip\s*code)\b", combined))
    has_phone = bool(re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", combined))

    # Check for missing basic seller identity on a checkout site
    policy_markers = policy_data.get("policy_terms") or {}
    has_contact = policy_markers.get("contact") or emails or has_phone or has_physical_address
    has_returns = policy_markers.get("returns") or return_days or has_no_refunds
    has_privacy = policy_markers.get("privacy") or "privacy" in combined

    if not has_contact and not has_returns and not has_privacy:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="high",
            rationale="Storefront omits all standard consumer protections: no contact info, refund policy, or privacy disclosures found.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"missing": ["contact", "returns", "privacy"]},
        )

    if conflicts:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Internal policy contradictions detected: {'; '.join(conflicts)}",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"conflicts": conflicts},
        )

    # Clean outcome: policies are coherent
    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale="Storefront policies and contact terms are internally consistent without detected contradictions.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=source_url,
        rule_version=RULE_VERSION,
        metadata={"return_days": return_days[0] if return_days else None, "has_contact": bool(has_contact)},
    )
