"""Deterministic domain age evaluation rule using RDAP data.

Classifies domain registration age with explicit fallback to "unknown"
whenever RDAP data is redacted, privacy-masked, or unavailable.
"""

from datetime import datetime, timezone
from typing import Any
import re
from app.schemas.findings import FindingModel

RULE_ID = "domain_age"
RULE_VERSION = "1.0.0"

# PROVISIONAL / UN-CALIBRATED: Age thresholds in days
YOUNG_DOMAIN_DAYS_CRITICAL = 14
YOUNG_DOMAIN_DAYS_ELEVATED = 60
ESTABLISHED_DOMAIN_DAYS = 180

def evaluate(
    rdap_data: dict[str, Any] | None,
    domain: str | None = None,
    evidence_id: str | None = None,
    reference_date: datetime | None = None,
) -> FindingModel:
    """Evaluate domain age from structured RDAP response."""
    now = reference_date or datetime.now(timezone.utc)

    if not rdap_data:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No RDAP registration data was provided or RDAP lookup was disabled.",
            rule_version=RULE_VERSION,
            source=domain,
            limitations=["RDAP lookup data missing or unattempted"],
        )

    if rdap_data.get("status") in {"unavailable", "error", "failed"}:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"RDAP query failed or was unavailable: {rdap_data.get('error', 'unknown error')}.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            limitations=["RDAP query failed or service unavailable"],
        )

    # Search for registration / creation date in standard RDAP fields
    # Standard RDAP events: [{"eventAction": "registration", "eventDate": "2024-01-01T..."}, ...]
    reg_date_str = None
    events = rdap_data.get("events") or []
    for ev in events:
        if ev.get("eventAction") in {"registration", "created", "creation"}:
            reg_date_str = ev.get("eventDate")
            break

    if not reg_date_str:
        # Fallback fields
        reg_date_str = (
            rdap_data.get("registration_date")
            or rdap_data.get("created_date")
            or rdap_data.get("creation_date")
        )

    if not reg_date_str:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="Domain registration date is redacted or not published in RDAP records.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            limitations=["Registration date redacted by registry/registrar"],
        )

    try:
        clean_date_str = str(reg_date_str).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"Could not parse RDAP event date '{reg_date_str}'.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            limitations=["Malformed registration timestamp"],
        )

    age_days = max(0, (now - dt).days)

    if age_days < YOUNG_DOMAIN_DAYS_CRITICAL:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="critical",
            rationale=f"Domain was registered only {age_days} day(s) ago (under {YOUNG_DOMAIN_DAYS_CRITICAL}-day critical provisional threshold).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            metadata={"age_days": age_days, "registration_date": dt.isoformat()},
        )

    if age_days < YOUNG_DOMAIN_DAYS_ELEVATED:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Domain was registered {age_days} days ago (newly created storefront under {YOUNG_DOMAIN_DAYS_ELEVATED} days).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            metadata={"age_days": age_days, "registration_date": dt.isoformat()},
        )

    if age_days >= ESTABLISHED_DOMAIN_DAYS:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Domain has an established registration history of {age_days} days ({age_days // 30} months).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=domain,
            rule_version=RULE_VERSION,
            metadata={"age_days": age_days, "registration_date": dt.isoformat()},
        )

    # Between 60 and 180 days: neutral / mild positive
    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale=f"Domain registration age is {age_days} days.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=domain,
        rule_version=RULE_VERSION,
        metadata={"age_days": age_days, "registration_date": dt.isoformat()},
    )
