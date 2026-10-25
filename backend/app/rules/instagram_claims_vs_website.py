"""Deterministic Instagram profile vs website identity cross-validation rule.

Compares user-supplied Instagram profile metadata (bio, bio link, handle)
with the retrieved public storefront attributes.
"""

from typing import Any
from urllib.parse import urlparse
from app.schemas.findings import FindingModel

RULE_ID = "instagram_claims_vs_website"
RULE_VERSION = "1.0.0"

def _extract_domain(url: str | None) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return (urlparse(url).hostname or "").rstrip(".").lower()

def evaluate(
    instagram_profile: dict[str, Any] | None,
    website_data: dict[str, Any] | None,
    evidence_id: str | None = None,
) -> FindingModel:
    """Evaluate cross-channel identity consistency between Instagram profile and storefront website."""
    if not instagram_profile:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No Instagram profile data provided for cross-channel identity verification.",
            rule_version=RULE_VERSION,
            limitations=["Instagram profile data missing"],
        )

    if not website_data:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="No website storefront data provided for cross-channel identity verification.",
            rule_version=RULE_VERSION,
            limitations=["Website data missing"],
        )

    handle = (instagram_profile.get("username") or instagram_profile.get("handle") or "").strip().lower().lstrip("@")
    bio_link = instagram_profile.get("external_url") or instagram_profile.get("bio_link") or ""
    site_url = website_data.get("url") or website_data.get("requested_url") or ""

    bio_domain = _extract_domain(bio_link)
    site_domain = _extract_domain(site_url)

    site_text = (website_data.get("text_excerpt") or "").lower()
    site_title = (website_data.get("title") or "").lower()

    # If neither bio link nor site URL could be compared
    if not bio_domain and not site_domain:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="unknown",
            severity="info",
            rationale="Neither Instagram bio link nor website domain could be parsed for comparison.",
            evidence_ids=[evidence_id] if evidence_id else [],
            rule_version=RULE_VERSION,
            limitations=["Missing URLs in profile and website inputs"],
        )

    # 1. Direct domain match between Instagram bio link and website
    domain_match = bool(bio_domain and site_domain and (bio_domain == site_domain or bio_domain.endswith("." + site_domain) or site_domain.endswith("." + bio_domain)))
    handle_on_site = bool(handle and (handle in site_text or handle in site_title))

    if domain_match and handle_on_site:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Bi-directional identity verified: Instagram links to '{site_domain}' and storefront references @{handle}.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=site_url,
            rule_version=RULE_VERSION,
            metadata={"bio_domain": bio_domain, "site_domain": site_domain, "handle": handle},
        )

    if domain_match and not handle_on_site:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="negative",
            severity="info",
            rationale=f"Instagram profile bio links directly to storefront domain '{site_domain}'.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=site_url,
            rule_version=RULE_VERSION,
            metadata={"bio_domain": bio_domain, "site_domain": site_domain},
        )

    # 2. Mismatch: Bio link points somewhere else (e.g. suspicious link shortener or unrelated site)
    if bio_domain and site_domain and not domain_match:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="medium",
            rationale=f"Channel mismatch: Instagram bio links to '{bio_domain}', but investigation storefront is '{site_domain}'.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=site_url,
            rule_version=RULE_VERSION,
            metadata={"bio_domain": bio_domain, "site_domain": site_domain},
        )

    # 3. Bio has no external website link at all
    if not bio_domain and site_domain:
        return FindingModel(
            rule_id=RULE_ID,
            outcome="positive",
            severity="low",
            rationale="Instagram profile does not publish a website link in bio, despite operating an active web storefront.",
            evidence_ids=[evidence_id] if evidence_id else [],
            source=site_url,
            rule_version=RULE_VERSION,
            metadata={"site_domain": site_domain},
        )

    return FindingModel(
        rule_id=RULE_ID,
        outcome="unknown",
        severity="info",
        rationale="Cross-channel comparison was inconclusive.",
        evidence_ids=[evidence_id] if evidence_id else [],
        rule_version=RULE_VERSION,
        limitations=["Inconclusive cross-channel indicators"],
    )
