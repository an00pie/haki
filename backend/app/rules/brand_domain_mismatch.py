"""Deterministic brand vs domain mismatch rule.

Compares claimed seller brand name against the hosting domain name,
taking into account multi-tenant e-commerce platform subdomains.
"""

import re
from urllib.parse import urlparse
from app.schemas.findings import FindingModel

RULE_ID = "brand_domain_mismatch"
RULE_VERSION = "1.0.0"

# Common hosted platform suffixes where the first subdomain is the merchant's identifier
PLATFORM_SUFFIXES = {
    "myshopify.com",
    "etsy.com",
    "wixsite.com",
    "instamojo.com",
    "dukann.com",
    "bigcommerce.com",
    "squarespace.com",
}

MAJOR_PROTECTED_BRANDS = {
    "apple", "nike", "samsung", "zara", "gucci", "rolex", "sony", "adidas",
    "louis vuitton", "chanel", "prada", "hermes", "dior", "ray-ban"
}

def _clean_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _extract_domain_and_subdomain(url_or_host: str) -> tuple[str, str, str]:
    if "://" in url_or_host:
        host = urlparse(url_or_host).hostname or ""
    else:
        host = url_or_host.split("/")[0].split(":")[0]
    host = host.rstrip(".").lower()
    
    parts = host.split(".")
    for platform in PLATFORM_SUFFIXES:
        if host.endswith("." + platform):
            prefix = host[: -len(platform) - 1]
            return host, prefix, platform

    # For standard domain: domain base is the second-to-last part or first part
    base = parts[-2] if len(parts) >= 2 else parts[0]
    tld = parts[-1] if len(parts) >= 2 else ""
    return host, base, tld

def evaluate(
    brand_name: str | None,
    domain_or_url: str | None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate whether claimed brand name contradicts or mismatches the storefront domain."""
    if not brand_name or not brand_name.strip():
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No brand name was provided to assess domain consistency.",
            rule_version=RULE_VERSION,
            limitations=["Brand name missing"],
        )

    if not domain_or_url or not domain_or_url.strip():
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No domain or URL was provided to assess brand consistency.",
            rule_version=RULE_VERSION,
            limitations=["Domain missing"],
        )

    host, identifier, platform_or_tld = _extract_domain_and_subdomain(domain_or_url)
    if not host:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale=f"Value '{domain_or_url}' could not be parsed as a valid domain.",
            rule_version=RULE_VERSION,
            limitations=["Unparseable domain"],
        )

    clean_brand = _clean_text(brand_name)
    clean_id = _clean_text(identifier)

    # 1. Platform subdomain match: e.g. "silkcraft" on "silkcraft.myshopify.com"
    if clean_brand in clean_id or clean_id in clean_brand:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Claimed brand '{brand_name}' matches storefront identifier '{identifier}' on '{host}'.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=host,
            rule_version=RULE_VERSION,
            metadata={"brand": brand_name, "identifier": identifier, "host": host},
        )

    # 2. Check if brand claims to be a major trademarked brand but runs on an unrelated domain
    brand_lower = brand_name.strip().lower()
    for protected in MAJOR_PROTECTED_BRANDS:
        if protected in brand_lower:
            # Does the domain contain the protected brand?
            if protected not in clean_id:
                return FindingModel(
                    rule_id=RULE_ID,
                    outcome="positive",
                    severity="high",
                    rationale=f"Claimed brand represents protected trademark '{protected.title()}', but storefront is hosted on unrelated domain '{host}'.",
                    evidence_ids=[evidence_id] if evidence_id else [],
                    source=host,
                    rule_version=RULE_VERSION,
                    metadata={"claimed_brand": brand_name, "protected_match": protected, "domain": host},
                )

    # 3. If brand keywords and domain tokens have common overlap
    brand_words = set(re.findall(r"[a-z0-9]{3,}", brand_lower))
    domain_words = set(re.findall(r"[a-z0-9]{3,}", identifier))
    overlap = brand_words.intersection(domain_words)

    if overlap:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Claimed brand '{brand_name}' shares identity tokens ({', '.join(sorted(overlap))}) with domain '{host}'.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=host,
            rule_version=RULE_VERSION,
            metadata={"overlap": sorted(list(overlap))},
        )

    # If completely distinct and no trademark claimed, it is not necessarily fraud (e.g. creative store name vs holding LLC domain)
    # Return unknown or mild observation with clear rationale
    return FindingModel(
        rule_id=RULE_ID,
        outcome="unknown",
        severity="low",
        rationale=f"Claimed brand '{brand_name}' does not directly match domain identifier '{identifier}', but no trademark violation was asserted.",
        evidence_ids=[evidence_id] if evidence_id else [],
        source=host,
        rule_version=RULE_VERSION,
        limitations=["Independent brand name and domain could not be definitively correlated"],
        metadata={"brand": brand_name, "domain": host},
    )
