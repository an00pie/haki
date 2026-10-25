"""Deterministic catalog incoherence detection rule.

Flags storefront catalogs that indiscriminately mix wildly disparate high-value categories
at implausible volume (characteristic of automated mass-scrape scam templates).
"""

from typing import Any
from app.schemas.findings import FindingModel

RULE_ID = "catalog_incoherence"
RULE_VERSION = "1.0.0"

# Broad category clusters
CATEGORY_CLUSTERS = {
    "electronics": {"phone", "laptop", "camera", "drone", "tablet", "audio", "tv", "charger", "gpu", "console"},
    "apparel": {"shirt", "dress", "shoes", "jacket", "hoodie", "pants", "kurti", "saree", "sneakers", "boots"},
    "heavy_machinery": {"chainsaw", "tractor", "generator", "welder", "lathe", "excavator", "compressor"},
    "luxury": {"rolex", "diamond", "gold", "luxury", "watch", "handbag", "patek", "louis vuitton"},
    "infant": {"baby", "stroller", "diaper", "crib", "pacifier", "infant", "toddler"},
}

def evaluate(
    products: list[dict[str, Any]] | None,
    source_url: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate whether the product catalog exhibits bizarre cross-category incoherence."""
    if not products or len(products) < 3:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="At least 3 catalog items are required to evaluate catalog category coherence.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Insufficient product items in catalog (fewer than 3)"],
        )

    # Map each product to matching category clusters
    matched_clusters = set()
    for item in products:
        title = (item.get("title") or item.get("name") or "").lower()
        desc = (item.get("description") or "").lower()
        text = f"{title} {desc}"

        for cluster_name, keywords in CATEGORY_CLUSTERS.items():
            if any(k in text for k in keywords):
                matched_clusters.add(cluster_name)

    # Flag if an unspecialized single merchant sells wildly incompatible clusters:
    # e.g. heavy machinery + baby diapers + luxury watches on a 5-item site
    incompatible_pairs = [
        ("heavy_machinery", "infant"),
        ("heavy_machinery", "luxury"),
        ("heavy_machinery", "apparel"),
    ]

    has_incompatible = any(c1 in matched_clusters and c2 in matched_clusters for c1, c2 in incompatible_pairs)

    if has_incompatible and len(products) <= 15:
        clusters_str = ", ".join(sorted(matched_clusters))
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Catalog displays incompatible category inventory ({clusters_str}) on a small storefront.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"clusters": list(matched_clusters), "product_count": len(products)},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale="Product catalog categories are coherent and industry-standard.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=source_url,
        rule_version=RULE_VERSION,
        metadata={"product_count": len(products), "clusters": list(matched_clusters)},
    )
