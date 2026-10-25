"""Deterministic public complaint synthesis rule.

Evaluates deduplicated search leads and public scam allegations.

CRITICAL RULE:
No results or empty search findings evaluate to "unknown", NEVER "negative" / safe.
Absence of public search findings is not proof of seller legitimacy.
"""

from typing import Any
from app.schemas.findings import FindingModel

RULE_ID = "public_complaints"
RULE_VERSION = "1.0.0"

def evaluate(
    complaint_leads: list[dict[str, Any]] | None,
    matched_identifier: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate public complaints and scam reports.

    Returns 'unknown' if no results or unattempted.
    Returns 'positive' if deduplicated corroborating complaint leads exist.
    """
    if not complaint_leads:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No public complaint leads were found or public search was unattempted. This is an unknown indicator, not proof of safety.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=matched_identifier,
            rule_version=RULE_VERSION,
            limitations=["Absence of public search results does not establish seller trustworthiness"],
        )

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for lead in complaint_leads:
        u = lead.get("url") or lead.get("source_url") or ""
        if u and u not in seen_urls:
            seen_urls.add(u)
            deduped.append(lead)
        elif not u:
            deduped.append(lead)

    if not deduped:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No valid complaint leads after deduplication. Outcome remains unknown.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=matched_identifier,
            rule_version=RULE_VERSION,
            limitations=["No deduplicated records found"],
        )

    count = len(deduped)
    sample_snippets = [item.get("snippet", "")[:120] for item in deduped[:2]]

    severity = "high" if count >= 3 else "medium"
    return FindingModel(
        rule_id=RULE_ID,
        outcome="positive",
        severity=severity,
        rationale=f"Found {count} deduplicated public complaint lead(s) matching '{matched_identifier or 'target'}'. Note: unverified public allegation snippets are treated as leads, not independent proof.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=matched_identifier,
        rule_version=RULE_VERSION,
        metadata={
            "matched_identifier": matched_identifier,
            "deduped_lead_count": count,
            "sample_snippets": sample_snippets,
        },
    )
