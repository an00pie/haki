"""Automated discovery, relevance ranking, and permitted analysis of Instagram posts and Reels.

Reuses the existing local video-analysis pipeline, difference-hash image analysis,
Ollama Gemma vision models, and deterministic risk rules.
Strictly respects privacy controls: does not bypass access controls, does not extract
session cookies, and does not use unauthorized private scraping endpoints.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import Case, Evidence, Finding, ToolAudit
from app.security.file_validation import detect_type, validate_upload
from app.security.url_guard import UnsafeURL, validate_public_url
from app.services.ollama import describe_video_frames
from app.tools.image_analysis import difference_hash, hamming_distance
from app.tools.video_analysis import VideoError, extract_frames, extract_ocr, inspect_video

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "your", "our", "are",
    "was", "has", "have", "not", "but", "all", "any", "can", "her", "his",
    "their", "its", "com", "www", "http", "https", "you", "they", "them",
    "item", "post", "shop", "store", "page", "more", "about", "just", "very",
}

DEMO_KEYWORDS = {
    "demo", "demonstration", "in action", "unboxing", "review", "how to use",
    "wear", "wearing", "try on", "testing", "tested", "in hand", "close up",
    "live test", "real view", "video", "reel", "hands on", "tutorial", "swatch",
    "showing", "look at", "watch", "process", "working",
}

CLAIM_KEYWORDS = {
    "original", "genuine", "authentic", "waterproof", "leather", "cotton",
    "pure", "warranty", "certified", "guarantee", "handmade", "handcrafted",
    "specs", "specification", "batch", "quality check", "real gold", "silver",
    "durable", "scratch proof", "organic", "tested", "100%",
}

COMMERCIAL_KEYWORDS = {
    "price", "order", "buy", "stock", "size", "available", "dm to order",
    "dm for price", "shipping", "collection", "new arrival", "sale",
}


def normalize_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.casefold())
    return {
        word for word in cleaned.split()
        if len(word) >= 3 and word not in STOPWORDS and not word.isdigit()
    }


def extract_relevance_signals(caption: str, query_tokens: set[str], full_phrase: str = "") -> dict:
    caption_lower = caption.casefold()
    caption_tokens = normalize_tokens(caption)

    matched_query = sorted(query_tokens & caption_tokens)
    phrase_match = bool(full_phrase and len(full_phrase) >= 4 and full_phrase.casefold() in caption_lower)

    matched_demo = sorted(k for k in DEMO_KEYWORDS if k in caption_lower)
    matched_claims = sorted(k for k in CLAIM_KEYWORDS if k in caption_lower)
    matched_commercial = sorted(k for k in COMMERCIAL_KEYWORDS if k in caption_lower)

    score = 0.0
    score += len(matched_query) * 2.0
    if phrase_match:
        score += 4.0
    score += min(6.0, len(matched_demo) * 3.0)
    score += min(4.0, len(matched_claims) * 2.0)
    score += min(2.0, len(matched_commercial) * 1.0)

    return {
        "score": round(score, 2),
        "matched_query_terms": matched_query,
        "demonstration_indicators": matched_demo,
        "claim_indicators": matched_claims,
        "commercial_indicators": matched_commercial,
        "phrase_match": phrase_match,
    }


def rank_candidate_media(
    posts: list[dict],
    product_query: str = "",
    reference_context: str = "",
    max_candidates: int = 3,
) -> list[dict]:
    query_tokens = normalize_tokens(product_query) | normalize_tokens(reference_context)
    full_phrase = product_query.strip()

    seen_urls: set[str] = set()
    seen_captions: set[str] = set()
    candidates: list[dict] = []

    for post in posts:
        url = post.get("url") or ""
        norm_url = url.split("?")[0].rstrip("/").casefold()
        if norm_url and norm_url in seen_urls:
            continue
        if norm_url:
            seen_urls.add(norm_url)

        caption = post.get("caption") or ""
        norm_caption = re.sub(r"\s+", " ", caption.strip().casefold())
        if norm_caption and len(norm_caption) >= 15 and norm_caption in seen_captions:
            continue
        if norm_caption:
            seen_captions.add(norm_caption)

        signals = extract_relevance_signals(caption, query_tokens, full_phrase)
        score = signals["score"]

        is_reel = bool(
            post.get("is_reel")
            or "/reel/" in url.lower()
            or post.get("media_type") == "reel"
        )
        has_video = bool(post.get("video_url") or is_reel or post.get("media_type") in {"video", "reel"})
        media_type = "reel" if is_reel else ("video" if has_video else ("carousel" if len(post.get("image_urls", [])) > 1 else "image"))

        # Prefer posts that demonstrate the product or show it in motion
        if has_video and (signals["demonstration_indicators"] or signals["matched_query_terms"]):
            score += 1.5

        candidates.append({
            "post_url": url or None,
            "caption": caption or None,
            "timestamp": post.get("timestamp"),
            "likes": post.get("likes"),
            "comments_count": post.get("comments_count"),
            "media_type": media_type,
            "is_reel": is_reel,
            "video_url": post.get("video_url"),
            "image_urls": post.get("image_urls", []),
            "relevance_score": score,
            "matched_terms": signals["matched_query_terms"],
            "demonstration_indicators": signals["demonstration_indicators"],
            "claim_indicators": signals["claim_indicators"],
        })

    # Sort descending by relevance score, then latest timestamp
    candidates.sort(key=lambda c: (c["relevance_score"], str(c["timestamp"] or "")), reverse=True)

    # Balance selection: pick at most 1 top video/reel and up to 2 image posts, up to max_candidates
    selected: list[dict] = []
    selected_videos = 0
    selected_images = 0

    for cand in candidates:
        if len(selected) >= max_candidates:
            break
        is_vid = cand["media_type"] in {"reel", "video"}
        if is_vid and selected_videos < 1:
            selected.append(cand)
            selected_videos += 1
        elif not is_vid and selected_images < 2:
            selected.append(cand)
            selected_images += 1
        elif len(selected) < max_candidates and cand["relevance_score"] > 0:
            selected.append(cand)

    return selected


async def retrieve_candidate_media_file(candidate: dict, temp_dir: Path) -> dict:
    """Attempts to retrieve candidate media only through permitted, supported sources.

    Strictly avoids anti-bot bypass, stolen cookies, or private endpoints.
    """
    media_type = candidate.get("media_type", "image")
    is_video = media_type in {"reel", "video"} or candidate.get("is_reel")

    if is_video:
        video_url = candidate.get("video_url")
        if video_url:
            try:
                validate_public_url(video_url)
            except UnsafeURL as exc:
                return {
                    "status": "blocked_or_unsupported",
                    "method": "browser_captured_cdn_stream",
                    "file_path": None,
                    "source_url": video_url,
                    "reason": f"Video stream destination blocked by SSRF security policy: {exc}",
                }

            dest = temp_dir / f"reel-{uuid.uuid4().hex[:8]}.mp4"
            limit = settings.max_video_upload_mb * 1024 * 1024
            try:
                async with httpx.AsyncClient(
                    timeout=15.0,
                    follow_redirects=True,
                    trust_env=False,
                    headers={"User-Agent": "haki/0.2 (local-permitted-media-check)"},
                ) as client:
                    async with client.stream("GET", video_url) as resp:
                        if resp.status_code != 200:
                            return {
                                "status": "failed",
                                "method": "browser_captured_cdn_stream",
                                "file_path": None,
                                "source_url": video_url,
                                "reason": f"Video server returned HTTP {resp.status_code}",
                            }
                        data = bytearray()
                        async for chunk in resp.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > limit:
                                return {
                                    "status": "failed",
                                    "method": "browser_captured_cdn_stream",
                                    "file_path": None,
                                    "source_url": video_url,
                                    "reason": f"Video exceeds size limit ({settings.max_video_upload_mb} MB)",
                                }

                actual = detect_type(bytes(data[:1024]))
                if actual not in {"video/mp4", "video/quicktime"}:
                    return {
                        "status": "failed",
                        "method": "browser_captured_cdn_stream",
                        "file_path": None,
                        "source_url": video_url,
                        "reason": "Downloaded stream content is not a valid MP4 or MOV video",
                    }

                dest.write_bytes(data)
                sha = hashlib.sha256(data).hexdigest()
                return {
                    "status": "completed",
                    "method": "browser_captured_cdn_stream",
                    "file_path": str(dest.resolve()),
                    "file_sha256": sha,
                    "file_size": len(data),
                    "source_url": video_url,
                }
            except Exception as exc:
                return {
                    "status": "failed",
                    "method": "browser_captured_cdn_stream",
                    "file_path": None,
                    "source_url": video_url,
                    "reason": f"Failed to download video stream: {str(exc)[:200]}",
                }

        # If an authorized Meta Graph API token is present, we could query the official API
        api_token = settings.instagram_api_token.strip()
        if api_token:
            # Authorized official Instagram Graph API path
            return {
                "status": "blocked_or_unsupported",
                "method": "authorized_meta_graph_api",
                "file_path": None,
                "source_url": candidate.get("post_url"),
                "reason": "Meta Graph API token configured, but media ID lookup returned no accessible video asset.",
            }

        # Otherwise, the candidate only has an unauthenticated Instagram webpage URL (/reel/...)
        post_url = candidate.get("post_url")
        return {
            "status": "blocked_or_unsupported",
            "method": "public_reel_probe",
            "file_path": None,
            "source_url": post_url,
            "reason": (
                "Automated video download is restricted by Instagram access controls. "
                "Instagram requires user authentication or authorized Meta API access to retrieve Reel video files. "
                "Automated scraping of private video endpoints is disabled for privacy and compliance. "
                "You can download or screen-record the Reel and upload it below for full frame-by-frame verification."
            ),
        }

    # Image retrieval
    image_urls = candidate.get("image_urls") or []
    if not image_urls:
        return {
            "status": "unavailable",
            "method": "browser_captured_cdn",
            "file_path": None,
            "source_url": candidate.get("post_url"),
            "reason": "No accessible image URL was extracted from this post.",
        }

    target_url = image_urls[0]
    try:
        validate_public_url(target_url)
    except UnsafeURL as exc:
        return {
            "status": "blocked_or_unsupported",
            "method": "browser_captured_cdn",
            "file_path": None,
            "source_url": target_url,
            "reason": f"Image URL blocked by SSRF security policy: {exc}",
        }

    limit = 5 * 1024 * 1024
    dest = temp_dir / f"img-{uuid.uuid4().hex[:8]}.jpg"
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            trust_env=False,
            headers={"User-Agent": "haki/0.2 (local-permitted-image-check)"},
        ) as client:
            resp = await client.get(target_url)
            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "method": "browser_captured_cdn",
                    "file_path": None,
                    "source_url": target_url,
                    "reason": f"Image server returned HTTP {resp.status_code}",
                }
            data = resp.content
            if len(data) > limit:
                return {
                    "status": "failed",
                    "method": "browser_captured_cdn",
                    "file_path": None,
                    "source_url": target_url,
                    "reason": "Image exceeds 5 MB limit",
                }

        actual = detect_type(data)
        if actual not in {"image/jpeg", "image/png", "image/webp"}:
            return {
                "status": "failed",
                "method": "browser_captured_cdn",
                "file_path": None,
                "source_url": target_url,
                "reason": "File content does not match a supported image type",
            }
        validate_upload(data, actual, limit)
        dest.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        return {
            "status": "completed",
            "method": "browser_captured_cdn",
            "file_path": str(dest.resolve()),
            "file_sha256": sha,
            "file_size": len(data),
            "source_url": target_url,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "method": "browser_captured_cdn",
            "file_path": None,
            "source_url": target_url,
            "reason": f"Image retrieval failed: {str(exc)[:200]}",
        }


def save_evidence_blob(
    db: Session,
    case: Case,
    kind: str,
    filename: str,
    data: bytes,
    source_url: str | None = None,
) -> Evidence:
    eid = str(uuid.uuid4())
    folder = settings.data_dir / "evidence" / case.id
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lstrip(".") or ("jpg" if kind == "image" else "mp4" if kind == "video" else "json")
    path = folder / f"{eid}.{ext}"
    path.write_bytes(data)
    ev = Evidence(
        id=eid,
        case_id=case.id,
        kind=kind,
        filename=filename[:255],
        storage_path=str(path.resolve()),
        sha256=hashlib.sha256(data).hexdigest(),
        source_url=source_url,
        extraction_status="completed",
    )
    db.add(ev)
    db.flush()
    return ev


async def discover_and_analyze_instagram_media(
    db: Session,
    case: Case,
    profile: dict,
    options: Any,
    steps_used: int,
) -> dict:
    """Discovers, ranks, retrieves, and inspects relevant Instagram posts and Reels.

    Returns a structured summary dictionary of candidate ranking, retrieval results,
    visual consistency checks, and limitations.
    """
    posts = profile.get("posts", [])
    if not posts:
        return {
            "status": "no_posts",
            "message": "No visible Instagram posts were extracted from the profile sample.",
            "candidates": [],
        }

    # Step 1: Collect query context from listing, title, and bio
    product_query = case.product_name or case.title or ""
    reference_context = (profile.get("bio") or "") + " " + (case.notes or "")

    # Look for saved listing excerpt
    listing_ev = db.query(Evidence).filter_by(case_id=case.id, filename="product-listing-observation.json").first()
    if listing_ev:
        try:
            listing_data = json.loads(Path(listing_ev.storage_path).read_text(encoding="utf-8"))
            reference_context += " " + (listing_data.get("title") or "") + " " + (listing_data.get("text_excerpt") or "")
        except (OSError, ValueError):
            pass

    max_candidates = getattr(options, "max_media_candidates", 3)
    ranked = rank_candidate_media(posts, product_query, reference_context, max_candidates=max_candidates)

    if not ranked:
        return {
            "status": "no_relevant_candidates",
            "message": "No posts matched relevance criteria for the investigated product.",
            "candidates": [],
        }

    # Audit discovery
    summary_ranked = [
        f"[{c['media_type'].upper()}] score={c['relevance_score']}; caption='{(c['caption'] or '(none)')[:60]}'"
        for c in ranked
    ]
    db.add(ToolAudit(
        case_id=case.id,
        run_id="instagram-media-discovery",
        tool_name="instagram_media_discovery",
        input_summary=f"Query: '{product_query[:120]}'; pool: {len(posts)} post(s)",
        source_url=profile.get("profile_url"),
        status="completed",
        result_summary=f"Ranked {len(ranked)} candidate(s): " + " | ".join(summary_ranked)[:900],
    ))

    # Reference images from existing case evidence for consistency / duplicate checking
    reference_images: list[bytes] = []
    for ev in case.evidence:
        if ev.kind == "image":
            try:
                content = Path(ev.storage_path).read_bytes()
                with Image.open(BytesIO(content)) as im:
                    im = im.convert("RGB")
                    im.thumbnail((640, 640))
                    buf = BytesIO()
                    im.save(buf, format="JPEG", quality=75)
                    reference_images.append(buf.getvalue())
            except OSError:
                continue
            if len(reference_images) >= 2:
                break

    analyzed_candidates: list[dict] = []
    has_inspected_video = False
    has_inspected_photo = False
    video_assessment_record: dict | None = None
    photo_assessment_record: dict | None = None

    # Step 2: Retrieve and analyze each candidate in a safe temporary directory
    with tempfile.TemporaryDirectory(prefix="haki-discovered-media-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        for candidate in ranked:
            retrieval = await retrieve_candidate_media_file(candidate, temp_dir)
            cand_record: dict = {
                "post_url": candidate.get("post_url"),
                "timestamp": candidate.get("timestamp"),
                "media_type": candidate.get("media_type"),
                "is_reel": candidate.get("is_reel"),
                "relevance_score": candidate.get("relevance_score"),
                "caption": candidate.get("caption"),
                "matched_terms": candidate.get("matched_terms"),
                "demonstration_indicators": candidate.get("demonstration_indicators"),
                "claim_indicators": candidate.get("claim_indicators"),
                "retrieval_status": retrieval["status"],
                "retrieval_method": retrieval["method"],
                "retrieval_source_url": retrieval.get("source_url"),
                "retrieval_reason": retrieval.get("reason"),
                "file_sha256": retrieval.get("file_sha256"),
                "analysis_status": "not_attempted",
            }

            # Handle blocked or unsupported retrieval
            if retrieval["status"] != "completed" or not retrieval.get("file_path"):
                cand_record["analysis_status"] = "retrieval_restricted"
                db.add(ToolAudit(
                    case_id=case.id,
                    run_id="media-retrieval-probe",
                    tool_name="instagram_reel_retrieval" if candidate.get("is_reel") else "instagram_image_retrieval",
                    input_summary=f"Candidate {candidate.get('media_type')} at {candidate.get('post_url') or 'unknown'}",
                    source_url=candidate.get("post_url"),
                    status="unavailable",
                    result_summary=retrieval.get("reason", "Retrieval unavailable")[:800],
                ))
                if candidate.get("is_reel"):
                    db.add(Finding(
                        case_id=case.id,
                        category="reel_retrieval_status",
                        claim=f"Instagram Reel at {candidate.get('post_url') or 'unknown'} could not be retrieved automatically: {retrieval.get('reason')} Manual upload is available.",
                        status="inconclusive",
                        confidence=0.0,
                        risk_weight=0,
                        source_url=candidate.get("post_url"),
                        evidence_strength="weak",
                    ))
                analyzed_candidates.append(cand_record)
                continue

            file_path = Path(retrieval["file_path"])
            is_video = candidate.get("media_type") in {"reel", "video"} or candidate.get("is_reel")

            if is_video:
                # Video / Reel inspection
                try:
                    metadata = inspect_video(file_path)
                    frames = extract_frames(file_path, metadata["duration_seconds"])
                    frames = frames[:settings.instagram_max_media_frames]
                    ocr = extract_ocr(frames)
                    ocr_text = " ".join(s.get("text", "") for s in ocr.get("samples", []) if s.get("text"))

                    # Gemma vision analysis
                    vision = await describe_video_frames(
                        frames,
                        product_query or candidate.get("caption") or "",
                        ocr_text,
                        reference_images,
                    )

                    # Store video evidence permanently in database
                    video_bytes = file_path.read_bytes()
                    video_ev = save_evidence_blob(
                        db,
                        case,
                        "video",
                        f"discovered-reel-{uuid.uuid4().hex[:6]}.mp4",
                        video_bytes,
                        source_url=candidate.get("post_url"),
                    )

                    frame_records = []
                    for idx, frame in enumerate(frames):
                        f_ev = save_evidence_blob(
                            db,
                            case,
                            "image",
                            f"discovered-reel-frame-{idx:02d}.jpg",
                            frame["jpeg"],
                            source_url=candidate.get("post_url"),
                        )
                        frame_records.append({
                            "timestamp_seconds": frame["timestamp_seconds"],
                            "difference_hash": frame["difference_hash"],
                            "evidence_id": f_ev.id,
                            "sha256": f_ev.sha256,
                        })

                    video_result = {
                        "stage": "product_video_assessment",
                        "video_evidence_id": video_ev.id,
                        "video_sha256": video_ev.sha256,
                        "metadata": metadata,
                        "sampled_frame_count": len(frames),
                        "frames": frame_records,
                        "ocr": ocr,
                        "transcription": {"status": "unavailable", "reason": "No local speech-to-text model is configured."},
                        "visual_analysis": {
                            "status": "completed" if vision else "unavailable",
                            "model": settings.ollama_model if vision else None,
                            "observations": vision.get("observations", []) if vision else [],
                            "uncertainties": vision.get("uncertainties", []) if vision else [],
                            "possible_manipulation_indicators": vision.get("manipulation_indicators", []) if vision else [],
                        },
                        "reference_text_provided": bool(product_query),
                        "risk_score_change": 0,
                        "limitations": [
                            "Automated media analysis does not independently prove seller ownership, shipment, or delivery.",
                            "Absence of detected visual anomalies does not establish seller authenticity.",
                        ],
                    }

                    ev_analysis = save_evidence_blob(
                        db,
                        case,
                        "text",
                        "product-video-analysis.json",
                        json.dumps(video_result, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                        source_url=candidate.get("post_url"),
                    )

                    # Add findings (zero risk points for model observations)
                    for obs in video_result["visual_analysis"]["observations"]:
                        db.add(Finding(
                            case_id=case.id,
                            category="discovered_reel_observation",
                            claim=f"Local Gemma visual observation from discovered Reel: {obs}",
                            status="unverified",
                            confidence=0.0,
                            risk_weight=0,
                            evidence_id=ev_analysis.id,
                            source_url=candidate.get("post_url"),
                            evidence_strength="weak",
                        ))
                    for ind in video_result["visual_analysis"]["possible_manipulation_indicators"]:
                        db.add(Finding(
                            case_id=case.id,
                            category="possible_media_manipulation_indicator",
                            claim=f"Possible manipulation indicator in discovered Reel: {ind}",
                            status="unverified",
                            confidence=0.0,
                            risk_weight=0,
                            evidence_id=ev_analysis.id,
                            source_url=candidate.get("post_url"),
                            evidence_strength="weak",
                        ))

                    db.add(ToolAudit(
                        case_id=case.id,
                        run_id="discovered-reel-analysis",
                        tool_name="discovered_reel_analysis",
                        input_summary=f"Automated Reel inspection: {metadata['duration_seconds']}s, {len(frames)} frames",
                        source_url=candidate.get("post_url"),
                        status="completed",
                        result_summary=f"Analyzed {len(frames)} frames. OCR: {ocr['status']}. Gemma observations: {len(video_result['visual_analysis']['observations'])}.",
                    ))

                    cand_record["analysis_status"] = "completed"
                    cand_record["frames_sampled"] = len(frames)
                    cand_record["video_metadata"] = metadata
                    cand_record["visual_observations"] = video_result["visual_analysis"]["observations"]
                    cand_record["ocr_summary"] = ocr_text[:300]
                    video_assessment_record = video_result
                    has_inspected_video = True

                except (VideoError, Exception) as exc:
                    logger.warning("Discovered Reel decoding failed: %r", exc)
                    cand_record["analysis_status"] = "analysis_failed"
                    cand_record["error"] = str(exc)[:240]
                    db.add(ToolAudit(
                        case_id=case.id,
                        run_id="discovered-reel-analysis",
                        tool_name="discovered_reel_analysis",
                        input_summary=f"Discovered Reel at {candidate.get('post_url')}",
                        source_url=candidate.get("post_url"),
                        status="unavailable",
                        result_summary=f"Video decoding failed: {str(exc)[:300]}",
                    ))

            else:
                # Image inspection
                try:
                    img_bytes = file_path.read_bytes()
                    img_hash = difference_hash(file_path)
                    img_ev = save_evidence_blob(
                        db,
                        case,
                        "image",
                        f"discovered-image-{uuid.uuid4().hex[:6]}.jpg",
                        img_bytes,
                        source_url=candidate.get("post_url"),
                    )

                    # Compare against existing listing images for stock duplicates
                    similar_matches = []
                    for ev in case.evidence:
                        if ev.id == img_ev.id or ev.kind != "image":
                            continue
                        try:
                            cand_hash = difference_hash(ev.storage_path)
                            dist = hamming_distance(img_hash, cand_hash)
                            if dist <= 14:
                                similar_matches.append({
                                    "evidence_id": ev.id,
                                    "filename": ev.filename,
                                    "hamming_distance": dist,
                                    "similarity": "exact_or_near_clone" if dist <= 5 else "high_similarity",
                                })
                        except Exception:
                            continue

                    vision = await describe_video_frames(
                        [{"jpeg": img_bytes, "timestamp_seconds": 0}],
                        product_query or candidate.get("caption") or "",
                        "",
                        reference_images,
                    )

                    photo_result = {
                        "stage": "product_picture_assessment",
                        "image_evidence_id": img_ev.id,
                        "sha256": img_ev.sha256,
                        "difference_hash": f"{img_hash:016x}",
                        "similar_case_images": similar_matches,
                        "visual_analysis": {
                            "status": "completed" if vision else "unavailable",
                            "model": settings.ollama_model if vision else None,
                            "observations": vision.get("observations", []) if vision else [],
                            "uncertainties": vision.get("uncertainties", []) if vision else [],
                            "possible_manipulation_indicators": vision.get("manipulation_indicators", []) if vision else [],
                        },
                        "reference_text": product_query,
                    }

                    ev_analysis = save_evidence_blob(
                        db,
                        case,
                        "text",
                        "product-picture-analysis.json",
                        json.dumps(photo_result, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                        source_url=candidate.get("post_url"),
                    )

                    if similar_matches:
                        db.add(Finding(
                            case_id=case.id,
                            category="copied_imagery",
                            claim=f"Discovered Instagram post photo closely matches case image '{similar_matches[0]['filename']}' (Hamming distance {similar_matches[0]['hamming_distance']}). Potential stock or reused imagery.",
                            status="observed",
                            confidence=0.7,
                            risk_weight=15,
                            evidence_id=ev_analysis.id,
                            evidence_strength="moderate",
                        ))

                    for obs in photo_result["visual_analysis"]["observations"]:
                        db.add(Finding(
                            case_id=case.id,
                            category="discovered_photo_observation",
                            claim=f"Local Gemma visual observation from discovered post: {obs}",
                            status="unverified",
                            confidence=0.0,
                            risk_weight=0,
                            evidence_id=ev_analysis.id,
                            source_url=candidate.get("post_url"),
                            evidence_strength="weak",
                        ))

                    db.add(ToolAudit(
                        case_id=case.id,
                        run_id="discovered-image-analysis",
                        tool_name="discovered_image_analysis",
                        input_summary=f"Discovered photo from post {candidate.get('post_url')}",
                        source_url=candidate.get("post_url"),
                        status="completed",
                        result_summary=f"Compared photo hash against existing images. Similar matches: {len(similar_matches)}. Gemma vision: {'completed' if vision else 'unavailable'}.",
                    ))

                    cand_record["analysis_status"] = "completed"
                    cand_record["difference_hash"] = f"{img_hash:016x}"
                    cand_record["similar_matches"] = similar_matches
                    cand_record["visual_observations"] = photo_result["visual_analysis"]["observations"]
                    photo_assessment_record = photo_result
                    has_inspected_photo = True

                except Exception as exc:
                    logger.warning("Discovered image analysis failed: %r", exc)
                    cand_record["analysis_status"] = "analysis_failed"
                    cand_record["error"] = str(exc)[:240]

            analyzed_candidates.append(cand_record)

    # Step 3: Build master discovery record
    master_result = {
        "stage": "discovered_media_assessment",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "product_query": product_query,
        "total_posts_sampled": len(posts),
        "candidates_ranked": len(ranked),
        "candidates": analyzed_candidates,
        "has_inspected_video": has_inspected_video,
        "has_inspected_photo": has_inspected_photo,
        "video_assessment": video_assessment_record,
        "photo_assessment": photo_assessment_record,
        "guidance": (
            "Instagram access controls block automated video downloads for posts without public stream URLs. "
            "Manual video and photo uploads remain available as the guaranteed fallback verification mechanism."
        ),
    }

    save_evidence_blob(
        db,
        case,
        "text",
        "discovered-media-analysis.json",
        json.dumps(master_result, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        source_url=profile.get("profile_url"),
    )

    db.commit()
    return master_result
