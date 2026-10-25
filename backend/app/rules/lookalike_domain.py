"""Deterministic lookalike domain detection rule.

Checks for typosquatting, homoglyph substitution, and brand keyword impersonation
against recognized e-commerce platforms and global retail brands.
"""

from typing import Any
from urllib.parse import urlparse
import unicodedata
from app.schemas.findings import FindingModel

RULE_ID = "lookalike_domain"
RULE_VERSION = "1.0.0"

# Legitimate authoritative brand domains and their root names
LEGITIMATE_BRANDS: dict[str, set[str]] = {
    "amazon": {"amazon.com", "amazon.in", "amazon.co.uk", "amazon.de", "amazon.ca", "amazon.co.jp"},
    "flipkart": {"flipkart.com"},
    "myntra": {"myntra.com"},
    "nike": {"nike.com"},
    "adidas": {"adidas.com", "adidas.co.in"},
    "apple": {"apple.com"},
    "samsung": {"samsung.com"},
    "zara": {"zara.com"},
    "meesho": {"meesho.com"},
    "shopify": {"shopify.com", "myshopify.com"},
    "walmart": {"walmart.com"},
    "ebay": {"ebay.com", "ebay.in"},
}

HOMOGLYPH_MAP = {
    "0": "o",
    "1": "l",
    "vv": "w",
    "а": "a", # Cyrillic
    "с": "c",
    "е": "e",
    "о": "o",
    "р": "p",
    "ѕ": "s",
    "і": "i",
    "ј": "j",
}

def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def _normalize_homoglyphs(text: str) -> str:
    nfkc = unicodedata.normalize("NFKC", text.lower())
    for k, v in HOMOGLYPH_MAP.items():
        nfkc = nfkc.replace(k, v)
    return nfkc

def _extract_domain(url_or_host: str) -> str:
    if "://" in url_or_host:
        p = urlparse(url_or_host)
        host = p.hostname or ""
    else:
        host = url_or_host.split("/")[0].split(":")[0]
    return host.rstrip(".").lower()

def evaluate(domain_or_url: str | None, evidence_id: str | None = None) -> FindingModel:
    """Evaluate whether domain is a lookalike impersonation of a well-known brand."""
    if not domain_or_url or not domain_or_url.strip():
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No domain or URL was provided to evaluate lookalike characteristics.",
            rule_version=RULE_VERSION,
            limitations=["Domain input missing or blank"],
        )

    host = _extract_domain(domain_or_url)
    if not host or "." not in host:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"Value '{domain_or_url}' could not be parsed as a valid domain name.",
            rule_version=RULE_VERSION,
            limitations=["Unparseable domain format"],
        )

    # 1. Check if it is an exact legitimate brand domain
    for brand, legit_domains in LEGITIMATE_BRANDS.items():
        if host in legit_domains or any(host.endswith("." + d) for d in legit_domains):
            return FindingModel(
                rule_id=RULE_ID,
                outcome="negative",
                severity="info",
                rationale=f"Domain '{host}' is an authoritative legitimate domain for {brand.title()}.",
                evidence_ids=[evidence_id] if evidence_id else [],
                source=host,
                rule_version=RULE_VERSION,
                metadata={"brand": brand, "match_type": "official_domain"},
            )

    # Extract base name before the public suffix / last dot
    parts = host.split(".")
    base_name = parts[-2] if len(parts) >= 2 else parts[0]
    normalized_base = _normalize_homoglyphs(base_name)

    # 2. Check for typosquatting / Levenshtein edit distance
    for brand in LEGITIMATE_BRANDS:
        # Exact match of brand name but on an unverified TLD (e.g. amazon.xyz or flipkart.biz)
        if base_name == brand or normalized_base == brand:
            return FindingModel(
                rule_id=RULE_ID,
                outcome="positive",
                severity="critical",
                rationale=f"Domain '{host}' uses the exact brand name '{brand}' with an unauthorized top-level domain.",
                evidence_ids=[evidence_id] if evidence_id else [],
                source=host,
                rule_version=RULE_VERSION,
                metadata={"impersonated_brand": brand, "type": "unauthorized_tld"},
            )

        # Look for edit distance 1 or 2 (e.g. arnazon, amzon, flipkaart)
        if len(brand) >= 4:
            dist = _levenshtein_distance(normalized_base, brand)
            if 1 <= dist <= 2 and abs(len(normalized_base) - len(brand)) <= 2:
                return FindingModel(
                    rule_id=RULE_ID,
                    outcome="positive",
                    severity="high",
                    rationale=f"Domain '{host}' is deceptively similar to brand '{brand}' (edit distance {dist}).",
                    evidence_ids=[evidence_id] if evidence_id else [],
                    source=host,
                    rule_version=RULE_VERSION,
                    metadata={"impersonated_brand": brand, "distance": dist, "type": "typosquatting"},
                )

        # Look for brand keyword containment with suspicious hyphens (e.g. amazon-sale, nike-outlet)
        if f"{brand}-" in normalized_base or f"-{brand}" in normalized_base or f"{brand}official" in normalized_base:
            return FindingModel(
                rule_id=RULE_ID,
                outcome="positive",
                severity="high",
                rationale=f"Domain '{host}' embeds protected brand keyword '{brand}' in a composite hostname.",
                evidence_ids=[evidence_id] if evidence_id else [],
                source=host,
                rule_version=RULE_VERSION,
                metadata={"impersonated_brand": brand, "type": "composite_brand_keyword"},
            )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="negative",
        severity="info",
        rationale=f"Domain '{host}' did not match any known lookalike or typosquatting patterns.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=host,
        rule_version=RULE_VERSION,
        metadata={"domain": host, "type": "independent_domain"},
    )
