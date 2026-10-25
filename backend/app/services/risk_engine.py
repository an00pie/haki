from collections import defaultdict
from app.services.scoring import score_investigation

# Illustrative, uncalibrated MVP weights. Signal families avoid duplicate scoring.
RISK_RULES_VERSION = "1.2.0"
WEIGHTS = {"corroborated_non_delivery": 30, "copied_imagery": 15,
           "archived_storefront_and_inaccessible": 5, "false_business_information": 20,
           "identity_changes_after_complaints": 15,
           "public_complaints": 25,"linked_domain":20,"payment_identity_mismatch":20,
           "profile_business_inconsistency":15,"image_reuse_context":10,
           "engagement_anomaly": 10,
           "instagram_account_maturity": 15,
           "instagram_follower_credibility": 15,
           "instagram_website_link": 15}
FAMILY = {"public_complaint_leads":"public_complaints",
          "rdap_domain_registration":"linked_domain",
          "wayback_archive_history":"linked_domain",
          "image_fingerprint":"image_reuse_context",
          "account_maturity_anomaly":"instagram_account_maturity",
          "follower_credibility_anomaly":"instagram_follower_credibility",
          "bio_website_anomaly":"instagram_website_link"}

OBSERVED_CATEGORIES = {
    "engagement_anomaly",
    "account_maturity_anomaly",
    "follower_credibility_anomaly",
    "bio_website_anomaly",
    "instagram_account_maturity",
    "instagram_follower_credibility",
    "instagram_website_link",
}

def assess(findings, audits=()):
    eligible = [f for f in findings if f.evidence_id and
                (f.status == "corroborated" or (f.status == "observed" and f.category in OBSERVED_CATEGORIES))]
    by_family = defaultdict(list)
    for f in eligible: by_family[FAMILY.get(f.category,f.category)].append(f)
    score = sum(min(WEIGHTS.get(k, 0), max([x.risk_weight for x in v] or [0])) for k, v in by_family.items())
    # An unavailable/dead site is only a low-weight contextual observation.
    score = min(100, score)
    corroborated=[f for f in eligible if f.status=="corroborated"]
    strength = "strong" if len(corroborated) >= 3 else "moderate" if corroborated else "weak"
    unavailable = sum(1 for a in audits if a.status == "unavailable")
    completed = sum(1 for a in audits if a.status == "completed")
    if any(a.tool_name=="engagement_sample_analysis" for a in audits):
        unattempted=sum(1 for a in audits if a.status=="not_requested")
    else:
        unattempted=max(0,2-completed-unavailable)
    if score >= 60: level = "elevated"
    elif score >= 30: level = "guarded"
    else: level = "limited"
    return {"risk_rules_version":RISK_RULES_VERSION,"risk_indicator": score, "risk_level": level, "label": "Provisional indicator (not a probability)",
            "evidence_strength": strength, "coverage": {"completed": completed, "unavailable": unavailable, "unattempted": unattempted},
            "factors": [{"category": k, "points": min(WEIGHTS.get(k, 0), max(x.risk_weight for x in v)), "finding_ids": [x.id for x in v]} for k,v in by_family.items()]}
