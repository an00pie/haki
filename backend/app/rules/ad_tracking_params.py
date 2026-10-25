"""Deterministic ad tracking parameter extraction rule.

CRITICAL RULE:
Ad tracking parameters (fbclid, gclid, ttclid, igshid, utm_*) indicate traffic provenance.
They are NEVER fraud evidence alone and contribute ZERO risk points to the score.
"""

from urllib.parse import urlparse, parse_qs
from app.schemas.findings import FindingModel

RULE_ID = "ad_tracking_params"
RULE_VERSION = "1.0.0"

KNOWN_TRACKING_KEYS = {
    "fbclid": "Meta / Facebook Click ID",
    "gclid": "Google Click ID",
    "ttclid": "TikTok Click ID",
    "igshid": "Instagram Share ID",
    "wbraid": "Google Web Attribution ID",
    "gbraid": "Google App Attribution ID",
    "utm_source": "UTM Source",
    "utm_medium": "UTM Medium",
    "utm_campaign": "UTM Campaign",
}

def evaluate(url: str | None, evidence_id: str | None = None) -> FindingModel:
    """Extract ad tracking parameters for provenance context without assigning fraud risk."""
    if not url or not url.strip():
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No URL was provided to inspect for tracking parameters.",
            rule_version=RULE_VERSION,
            limitations=["URL missing"],
        )

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    detected = {}
    for key, val in query_params.items():
        k_lower = key.lower()
        if k_lower in KNOWN_TRACKING_KEYS:
            detected[k_lower] = {"label": KNOWN_TRACKING_KEYS[k_lower], "value": val[0] if val else ""}

    if detected:
        labels = [d["label"] for d in detected.values()]
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="info",
            rationale=(
                f"Ad tracking parameter(s) detected: {', '.join(labels)}. "
                "This indicates ad or campaign traffic provenance; it is never evidence of fraud "
                "and assigns 0 risk points."
            ),
            evidence_ids=[evidence_id] if evidence_id else [],
            source=url,
            rule_version=RULE_VERSION,
            metadata={"tracking_params": list(detected.keys()), "risk_contribution": 0},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale="No ad tracking or campaign attribution parameters found in URL.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=url,
        rule_version=RULE_VERSION,
        metadata={"risk_contribution": 0},
    )
