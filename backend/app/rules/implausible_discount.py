"""Deterministic implausible discount evaluation rule.

Flags extreme or economically implausible markdowns (e.g., 90%+ off luxury/electronics)
with strict fallback to "unknown" when reference or original prices are missing.
"""

from typing import Any
from app.schemas.findings import FindingModel

RULE_ID = "implausible_discount"
RULE_VERSION = "1.0.0"

# PROVISIONAL / UN-CALIBRATED: Discount threshold percentages
CRITICAL_DISCOUNT_PERCENT = 85.0
ELEVATED_DISCOUNT_PERCENT = 75.0

def evaluate(
    sale_price: float | None,
    original_price: float | None = None,
    reference_price: float | None = None,
    product_name: str | None = None,
    source_url: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate whether an advertised discount is implausibly steep."""
    benchmark = original_price if (original_price and original_price > 0) else reference_price

    if sale_price is None or sale_price <= 0 or benchmark is None or benchmark <= 0:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="Original list price or reference market price is missing; discount cannot be evaluated.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Missing baseline/reference price for comparison"],
        )

    if sale_price >= benchmark:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Item is sold at regular or non-discounted pricing ({sale_price} vs reference {benchmark}).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"sale_price": sale_price, "reference_price": benchmark, "discount_percent": 0.0},
        )

    discount_pct = ((benchmark - sale_price) / benchmark) * 100.0

    if discount_pct >= CRITICAL_DISCOUNT_PERCENT:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="high",
            rationale=f"Implausibly steep discount of {discount_pct:.1f}% (reduced from {benchmark} to {sale_price}).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"discount_percent": round(discount_pct, 1), "sale_price": sale_price, "reference_price": benchmark},
        )

    if discount_pct >= ELEVATED_DISCOUNT_PERCENT:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Steep markdown of {discount_pct:.1f}% detected (from {benchmark} to {sale_price}).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"discount_percent": round(discount_pct, 1), "sale_price": sale_price, "reference_price": benchmark},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale=f"Discount of {discount_pct:.1f}% is within plausible commercial retail expectations.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=source_url,
        rule_version=RULE_VERSION,
        metadata={"discount_percent": round(discount_pct, 1), "sale_price": sale_price, "reference_price": benchmark},
    )
