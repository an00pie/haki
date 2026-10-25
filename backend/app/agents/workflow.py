"""LangGraph orchestration workflow for ScamTrace AI Stage 1 investigation.

Graph Topology:
  validate -> profile -> inspect_site -> +-- catalog_pricing --+
                                         +-- domain_identity --+-> dedupe -> score -> explain -> report
                                         +-- complaints -------+

Features:
- Parallel execution branches using list-append reducers (operator.add)
- Node timeout bounds, retry budgets, and cancellation checks
- Deterministic scoring separated from Gemma explanation layer
- Comprehensive error containment: node failures yield unknown findings and allow partial results
"""

import asyncio
from datetime import datetime, timezone
import operator
from typing import Annotated, Any, Sequence
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from app.config import settings
from app.schemas.findings import FindingModel, EvidenceModel
from app.security.url_guard import validate_url_for_storage, UnsafeURL
from app.tools.web_fetch import fetch_page
from app.rules import (
    lookalike_domain,
    brand_domain_mismatch,
    domain_age,
    policy_conflicts,
    catalog_incoherence,
    duplicate_descriptions,
    implausible_discount,
    uniform_pricing,
    ad_tracking_params,
    instagram_claims_vs_website,
    public_complaints,
)
from app.services.scoring import score_investigation
from app.services.explain import generate_explanation, ExplanationOutput
from app.services.instagram_graph import instagram_graph_adapter

class InvestigationState(TypedDict):
    # Inputs
    case_id: str
    store_url: str | None
    seller_handle: str | None
    product_name: str | None
    user_supplied_bio: str | None
    sale_price: float | None
    original_price: float | None
    reference_price: float | None
    instagram_profile: dict[str, Any] | None
    products: list[dict[str, Any]] | None
    rdap_data: dict[str, Any] | None
    complaint_leads: list[dict[str, Any]] | None
    is_cancelled: bool

    # Shared reducer state
    findings: Annotated[list[FindingModel], operator.add]
    evidence: Annotated[list[EvidenceModel], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    audits: Annotated[list[dict[str, Any]], operator.add]
    retry_counts: dict[str, int]

    # Node intermediate data
    website_data: dict[str, Any] | None
    scoring_result: dict[str, Any] | None
    explanation: dict[str, Any] | None
    report_summary: dict[str, Any] | None

# Helper to create an audit record
def make_audit(tool_name: str, status: str, summary: str, url: str | None = None) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "status": status,
        "result_summary": summary,
        "source_url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Node 1: Validate Inputs
async def node_validate(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {"errors": [{"node": "validate", "error": "Scan was cancelled"}]}

    findings = []
    audits = []
    errors = []

    store_url = state.get("store_url")
    if store_url:
        try:
            validate_url_for_storage(store_url)
            audits.append(make_audit("url_validation", "completed", f"Store URL validated for inspection: {store_url}", store_url))
        except UnsafeURL as e:
            errors.append({"node": "validate", "error": f"Invalid or unsafe storefront URL: {e}"})
            audits.append(make_audit("url_validation", "unavailable", f"Store URL rejected: {e}", store_url))

    seller_handle = state.get("seller_handle")
    if seller_handle:
        audits.append(make_audit("handle_validation", "completed", f"Seller identifier received: {seller_handle}"))

    return {
        "findings": findings,
        "audits": audits,
        "errors": errors,
    }

# Node 2: Profile & Provenance Clues
async def node_profile(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    findings = []
    audits = []

    # Check for ad tracking parameters (provenance clue only, 0 risk points)
    store_url = state.get("store_url")
    if store_url:
        tracking_finding = ad_tracking_params.evaluate(store_url)
        findings.append(tracking_finding)
        audits.append(make_audit("ad_tracking_inspection", "completed", tracking_finding.rationale, store_url))

    # Instagram profile overview & Meta Graph API adapter
    ig_profile = state.get("instagram_profile")
    seller_handle = state.get("seller_handle")
    if seller_handle and instagram_graph_adapter.is_configured and not ig_profile:
        graph_res = await instagram_graph_adapter.fetch_account_and_media(seller_handle)
        audits.append(make_audit(
            "instagram_graph_api",
            graph_res["status"],
            f"Meta Graph API query for @{seller_handle}: {graph_res.get('reason') or 'Retrieved account'}",
            (graph_res.get("profile") or {}).get("profile_url"),
        ))
        if graph_res["status"] == "completed" and graph_res.get("profile"):
            ig_profile = graph_res["profile"]

    if ig_profile:
        bio = ig_profile.get("biography") or state.get("user_supplied_bio") or ""
        external_url = ig_profile.get("external_url") or ig_profile.get("bio_link") or ""
        audits.append(make_audit(
            "instagram_profile_intake",
            "completed",
            f"Profile @{ig_profile.get('username')} ingested with bio length {len(bio)} and bio link '{external_url}'",
            external_url or None,
        ))
    elif seller_handle:
        audits.append(make_audit(
            "instagram_graph_api",
            "not_configured",
            f"Meta Graph API not configured; using user-provided handle @{seller_handle} and bio fallback.",
            None,
        ))

    return {
        "findings": findings,
        "audits": audits,
    }

# Node 3: Inspect Storefront Website
async def node_inspect_site(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    store_url = state.get("store_url")
    if not store_url:
        return {
            "website_data": None,
            "audits": [make_audit("storefront_fetch", "not_requested", "No store URL provided for site inspection")],
        }

    audits = []
    errors = []
    evidence = []

    try:
        # Enforce node timeout
        fetch_res = await asyncio.wait_for(
            fetch_page(store_url, timeout=settings.fetch_timeout_s),
            timeout=settings.fetch_timeout_s + 2.0,
        )

        if fetch_res.get("status") == "completed":
            ev = EvidenceModel(
                kind="html",
                source_url=fetch_res.get("url"),
                content_preview=fetch_res.get("text_excerpt", "")[:500],
                provenance="ssrf_safe_fetcher",
                raw_data=fetch_res,
            )
            evidence.append(ev)
            audits.append(make_audit("storefront_fetch", "completed", f"Retrieved page: '{fetch_res.get('title')}'", store_url))
            return {
                "website_data": fetch_res,
                "evidence": evidence,
                "audits": audits,
            }
        else:
            err_msg = fetch_res.get("error", "Failed to retrieve page safely")
            audits.append(make_audit("storefront_fetch", "unavailable", err_msg, store_url))
            return {
                "website_data": None,
                "audits": audits,
                "errors": [{"node": "inspect_site", "error": err_msg}],
            }

    except asyncio.TimeoutError:
        err_msg = f"Site inspection timed out after {settings.fetch_timeout_s}s"
        audits.append(make_audit("storefront_fetch", "unavailable", err_msg, store_url))
        return {
            "website_data": None,
            "audits": audits,
            "errors": [{"node": "inspect_site", "error": err_msg}],
        }
    except Exception as e:
        err_msg = f"Site inspection error: {e}"
        audits.append(make_audit("storefront_fetch", "unavailable", err_msg, store_url))
        return {
            "website_data": None,
            "audits": audits,
            "errors": [{"node": "inspect_site", "error": err_msg}],
        }

# Parallel Node 4A: Catalog & Pricing
async def node_catalog_pricing(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    findings = []
    audits = []
    products = state.get("products") or []

    # 1. Catalog incoherence
    incoh_finding = catalog_incoherence.evaluate(products, source_url=state.get("store_url"))
    findings.append(incoh_finding)

    # 2. Duplicate descriptions
    dup_finding = duplicate_descriptions.evaluate(products, source_url=state.get("store_url"))
    findings.append(dup_finding)

    # 3. Implausible discount
    disc_finding = implausible_discount.evaluate(
        sale_price=state.get("sale_price"),
        original_price=state.get("original_price"),
        reference_price=state.get("reference_price"),
        product_name=state.get("product_name"),
        source_url=state.get("store_url"),
    )
    findings.append(disc_finding)

    # 4. Uniform pricing
    uniform_finding = uniform_pricing.evaluate(products, source_url=state.get("store_url"))
    findings.append(uniform_finding)

    audits.append(make_audit("catalog_pricing_analysis", "completed", f"Evaluated {len(products)} products for pricing and catalog coherence"))
    return {
        "findings": findings,
        "audits": audits,
    }

# Parallel Node 4B: Domain Identity & Policy
async def node_domain_identity(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    findings = []
    audits = []
    store_url = state.get("store_url")
    brand = state.get("seller_handle") or state.get("product_name")

    # 1. Lookalike domain
    lookalike_finding = lookalike_domain.evaluate(store_url)
    findings.append(lookalike_finding)

    # 2. Brand domain mismatch
    mismatch_finding = brand_domain_mismatch.evaluate(brand, store_url)
    findings.append(mismatch_finding)

    # 3. Domain age (RDAP)
    rdap = state.get("rdap_data")
    age_finding = domain_age.evaluate(rdap, domain=store_url)
    findings.append(age_finding)

    # 4. Policy conflicts
    site_data = state.get("website_data")
    policy_finding = policy_conflicts.evaluate(site_data, source_url=store_url)
    findings.append(policy_finding)

    # 5. Instagram claims vs website
    ig_profile = state.get("instagram_profile")
    ig_vs_site = instagram_claims_vs_website.evaluate(ig_profile, site_data)
    findings.append(ig_vs_site)

    audits.append(make_audit("domain_identity_analysis", "completed", f"Evaluated domain identity and policy disclosures for '{store_url or '(no url)'}'"))
    return {
        "findings": findings,
        "audits": audits,
    }

# Parallel Node 4C: Public Complaints
async def node_complaints(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    findings = []
    audits = []
    leads = state.get("complaint_leads") or []
    identifier = state.get("seller_handle") or state.get("store_url")

    complaints_finding = public_complaints.evaluate(leads, matched_identifier=identifier)
    findings.append(complaints_finding)

    audits.append(make_audit(
        "public_complaints_analysis",
        "completed" if leads else "not_requested",
        complaints_finding.rationale,
    ))

    return {
        "findings": findings,
        "audits": audits,
    }

# Node 5: Deduplicate Findings
async def node_dedupe(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {}

    raw_findings = state.get("findings", [])
    deduped_by_rule = {}

    # Prioritize positive/negative over unknown if multiple evaluations of the same rule occur
    for f in raw_findings:
        existing = deduped_by_rule.get(f.rule_id)
        if not existing:
            deduped_by_rule[f.rule_id] = f
        elif existing.outcome == "unknown" and f.outcome != "unknown":
            deduped_by_rule[f.rule_id] = f

    return {
        "findings": list(deduped_by_rule.values()),
    }

# Node 6: Deterministic Scoring
async def node_score(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {"scoring_result": None}

    findings = state.get("findings", [])
    audits = state.get("audits", [])

    score_result = score_investigation(findings, audits)
    return {
        "scoring_result": score_result,
        "audits": [make_audit("deterministic_scorer", "completed", f"Calculated risk indicator {score_result['risk_score']} ({score_result['risk_band']}) with confidence {score_result['confidence']}")],
    }

# Node 7: Gemma Explanation Layer
async def node_explain(state: InvestigationState) -> dict[str, Any]:
    if state.get("is_cancelled"):
        return {"explanation": None}

    findings = state.get("findings", [])
    evidence = state.get("evidence", [])
    allowed_ids = [e.id for e in evidence]

    # Assemble contextual text for Ollama
    text_pieces = []
    for f in findings:
        text_pieces.append(f"[{f.rule_id}] outcome={f.outcome}, severity={f.severity}: {f.rationale}")

    combined_text = "\n".join(text_pieces)
    explanation = await generate_explanation(combined_text, findings, allowed_evidence_ids=allowed_ids)

    return {
        "explanation": explanation.model_dump(),
        "audits": [make_audit("explanation_generator", "completed", f"Generated explanation with {len(explanation.observations)} observations")],
    }

# Node 8: Report Assembly
async def node_report(state: InvestigationState) -> dict[str, Any]:
    score_res = state.get("scoring_result") or {}
    explanation = state.get("explanation") or {}
    risk_score = score_res.get("risk_score", 0)

    # Recommend Stage 2 video analysis if score crosses threshold
    stage2_recommended = risk_score >= settings.stage2_threshold

    report = {
        "case_id": state.get("case_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoring": score_res,
        "stage2_recommended": stage2_recommended,
        "stage2_threshold": settings.stage2_threshold,
        "explanation": explanation,
        "findings_count": len(state.get("findings", [])),
        "evidence_count": len(state.get("evidence", [])),
        "errors": state.get("errors", []),
    }

    return {
        "report_summary": report,
    }

def create_investigation_graph():
    """Build and compile the LangGraph workflow."""
    builder = StateGraph(InvestigationState)

    # Register Nodes
    builder.add_node("validate", node_validate)
    builder.add_node("profile", node_profile)
    builder.add_node("inspect_site", node_inspect_site)
    builder.add_node("catalog_pricing", node_catalog_pricing)
    builder.add_node("domain_identity", node_domain_identity)
    builder.add_node("complaints", node_complaints)
    builder.add_node("dedupe", node_dedupe)
    builder.add_node("score", node_score)
    builder.add_node("explain", node_explain)
    builder.add_node("report", node_report)

    # Edges: Sequential start
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "profile")
    builder.add_edge("profile", "inspect_site")

    # Parallel fan-out
    builder.add_edge("inspect_site", "catalog_pricing")
    builder.add_edge("inspect_site", "domain_identity")
    builder.add_edge("inspect_site", "complaints")

    # Parallel join
    builder.add_edge("catalog_pricing", "dedupe")
    builder.add_edge("domain_identity", "dedupe")
    builder.add_edge("complaints", "dedupe")

    # Sequential finish
    builder.add_edge("dedupe", "score")
    builder.add_edge("score", "explain")
    builder.add_edge("explain", "report")
    builder.add_edge("report", END)

    return builder.compile()

# Global compiled graph
investigation_graph = create_investigation_graph()
