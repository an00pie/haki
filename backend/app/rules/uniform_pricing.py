"""Deterministic uniform catalog pricing detection rule.

Flags catalogs where all items across disparate product types carry identical flat prices
(common signature of fraudulent flat-rate liquidation storefronts).
"""

from typing import Any
from app.schemas.findings import FindingModel

RULE_ID = "uniform_pricing"
RULE_VERSION = "1.0.0"

MIN_CATALOG_ITEMS = 3

def evaluate(
    products: list[dict[str, Any]] | None,
    source_url: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate whether the catalog exhibits suspicious flat-rate uniform pricing."""
    if not products or len(products) < MIN_CATALOG_ITEMS:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"At least {MIN_CATALOG_ITEMS} priced products are required to evaluate pricing variation.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=[f"Fewer than {MIN_CATALOG_ITEMS} items provided in catalog"],
        )

    prices = []
    for item in products:
        p = item.get("price") or item.get("sale_price") or item.get("amount")
        try:
            val = float(p)
            if val > 0:
                prices.append(val)
        except (ValueError, TypeError):
            continue

    if len(prices) < MIN_CATALOG_ITEMS:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"Fewer than {MIN_CATALOG_ITEMS} items have valid numerical prices.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Insufficient numerical price data"],
        )

    unique_prices = set(prices)

    if len(unique_prices) == 1:
        uniform_val = prices[0]
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"All {len(prices)} inspected items carry an identical flat price of {uniform_val}.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"item_count": len(prices), "flat_price": uniform_val},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale=f"Catalog displays varied, item-specific pricing across {len(prices)} items ({len(unique_prices)} distinct prices).",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=source_url,
        rule_version=RULE_VERSION,
        metadata={"item_count": len(prices), "unique_prices": len(unique_prices)},
    )
