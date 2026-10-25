"""Deterministic duplicate product description detection rule.

Detects verbatim identical description texts copy-pasted across distinct catalog items.
"""

from typing import Any
import re
from collections import defaultdict
from app.schemas.findings import FindingModel

RULE_ID = "duplicate_descriptions"
RULE_VERSION = "1.0.0"

MIN_DESCRIPTION_LENGTH = 50

def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned

def evaluate(
    products: list[dict[str, Any]] | None,
    source_url: str | None = None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate whether multiple distinct products reuse identical boilerplate description text."""
    if not products or len(products) < 2:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="At least 2 products with descriptions are required to evaluate description duplication.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Fewer than 2 products provided"],
        )

    desc_to_products = defaultdict(list)
    valid_descriptions_count = 0

    for item in products:
        title = item.get("title") or item.get("name") or "(untitled)"
        desc = item.get("description") or ""
        norm = _normalize_text(desc)
        if len(norm) >= MIN_DESCRIPTION_LENGTH:
            valid_descriptions_count += 1
            desc_to_products[norm].append(title)

    if valid_descriptions_count < 2:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"Catalog has fewer than 2 items with detailed descriptions (minimum {MIN_DESCRIPTION_LENGTH} chars).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            limitations=["Product descriptions missing or too short"],
        )

    # Check for identical descriptions across distinct titles
    duplicate_groups = {desc: titles for desc, titles in desc_to_products.items() if len(titles) >= 2}

    if duplicate_groups:
        worst_count = max(len(t) for t in duplicate_groups.values())
        sample_titles = list(duplicate_groups.values())[0][:3]
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Found verbatim duplicate description text shared across {worst_count} distinct products (e.g. {', '.join(sample_titles)}).",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=source_url,
            rule_version=RULE_VERSION,
            metadata={"duplicate_group_count": len(duplicate_groups), "max_reused_items": worst_count},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale="Product descriptions are individually customized without verbatim duplication.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=source_url,
        rule_version=RULE_VERSION,
        metadata={"inspected_items": valid_descriptions_count},
    )
