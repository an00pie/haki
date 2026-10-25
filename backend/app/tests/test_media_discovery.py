import json
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.media_discovery import (
    rank_candidate_media,
    extract_relevance_signals,
    retrieve_candidate_media_file,
    normalize_tokens,
)
from app.tools.video_analysis import extract_frames, inspect_video

client = TestClient(app)

def make_test_clip(path: Path, duration="2"):
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi",
            "-i", f"testsrc2=size=160x120:rate=2:duration={duration}",
            "-an", "-c:v", "mpeg4", "-threads", "1", "-y", str(path)
        ],
        check=True,
        timeout=15,
    )
    return path


def test_relevance_signals_and_token_normalization():
    tokens = normalize_tokens("Luxury Handmade Leather Handbag with 2 Year Warranty")
    assert "luxury" in tokens
    assert "leather" in tokens
    assert "handbag" in tokens
    assert "warranty" in tokens
    assert "with" not in tokens  # stopword

    signals = extract_relevance_signals(
        caption="Live unboxing and review of our genuine leather handbag! Waterproof test included.",
        query_tokens={"leather", "handbag"},
        full_phrase="leather handbag",
    )
    assert signals["score"] >= 8.0
    assert "unboxing" in signals["demonstration_indicators"] or "review" in signals["demonstration_indicators"]
    assert "genuine" in signals["claim_indicators"] or "waterproof" in signals["claim_indicators"]
    assert signals["phrase_match"] is True


def test_media_ranking_prefers_relevant_and_demo_posts():
    posts = [
        {
            "url": "https://www.instagram.com/p/generic1/",
            "caption": "Good morning coffee and sunshine #vibes",
            "media_type": "image",
            "image_urls": ["https://cdn.example/coffee.jpg"],
        },
        {
            "url": "https://www.instagram.com/p/product_pic/",
            "caption": "New arrival! Leather handbag in black, size medium. DM for price.",
            "media_type": "image",
            "image_urls": ["https://cdn.example/bag.jpg"],
        },
        {
            "url": "https://www.instagram.com/reel/demo_reel/",
            "caption": "Full demonstration of our genuine leather handbag in action! Unboxing and scratch test.",
            "is_reel": True,
            "media_type": "reel",
            "video_url": "https://cdn.example/bag_demo.mp4",
        },
    ]

    ranked = rank_candidate_media(
        posts=posts,
        product_query="leather handbag",
        reference_context="High quality genuine leather handbag collection",
        max_candidates=3,
    )

    assert len(ranked) >= 2
    # The demonstration Reel should rank first due to demo keywords, claim signals, and reel bonus
    assert ranked[0]["is_reel"] is True
    assert ranked[0]["post_url"] == "https://www.instagram.com/reel/demo_reel/"
    assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]
    assert "unboxing" in ranked[0]["demonstration_indicators"] or "demonstration" in ranked[0]["demonstration_indicators"]


def test_media_ranking_deduplicates_duplicate_urls_and_captions():
    posts = [
        {
            "url": "https://www.instagram.com/p/ABC123/",
            "caption": "Exclusive luxury blue sapphire ring certified 100% natural.",
            "media_type": "image",
        },
        {
            "url": "https://www.instagram.com/p/ABC123/?utm_source=ig_web",  # duplicate URL
            "caption": "Exclusive luxury blue sapphire ring certified 100% natural.",
            "media_type": "image",
        },
        {
            "url": "https://www.instagram.com/p/DIFFERENT_URL/",
            "caption": "Exclusive luxury blue sapphire ring certified 100% natural.",  # duplicate caption
            "media_type": "image",
        },
    ]

    ranked = rank_candidate_media(
        posts=posts,
        product_query="sapphire ring",
        reference_context="",
        max_candidates=3,
    )

    assert len(ranked) == 1


@pytest.mark.anyio
async def test_permitted_retrieval_browser_captured_cdn(tmp_path, monkeypatch):
    clip = make_test_clip(tmp_path / "valid_clip.mp4")
    clip_bytes = clip.read_bytes()

    class MockStreamResponse:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_bytes(self):
            yield clip_bytes

    class MockClient:
        def stream(self, method, url):
            return MockStreamResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())

    candidate = {
        "media_type": "reel",
        "is_reel": True,
        "video_url": "https://scontent.cdninstagram.com/reel123.mp4",
        "post_url": "https://www.instagram.com/reel/123/",
    }

    result = await retrieve_candidate_media_file(candidate, tmp_path)
    assert result["status"] == "completed"
    assert result["method"] == "browser_captured_cdn_stream"
    assert result["file_path"] is not None
    assert Path(result["file_path"]).exists()
    assert result["file_size"] == len(clip_bytes)
    assert len(result["file_sha256"]) == 64


@pytest.mark.anyio
async def test_blocked_reel_page_returns_clear_explanation_without_bypassing_auth(tmp_path):
    candidate = {
        "media_type": "reel",
        "is_reel": True,
        "video_url": None,  # No direct stream URL rendered
        "post_url": "https://www.instagram.com/reel/Cxyz987/",
    }

    result = await retrieve_candidate_media_file(candidate, tmp_path)
    assert result["status"] == "blocked_or_unsupported"
    assert result["method"] == "public_reel_probe"
    assert result["file_path"] is None
    assert "access controls" in result["reason"].lower()
    assert "upload" in result["reason"].lower()


@pytest.mark.anyio
async def test_ssrf_and_privacy_controls_enforced(tmp_path):
    # Attempt SSRF via loopback/internal IP in video_url
    candidate = {
        "media_type": "reel",
        "is_reel": True,
        "video_url": "http://127.0.0.1:8000/private_stream.mp4",
        "post_url": "https://www.instagram.com/reel/private/",
    }

    result = await retrieve_candidate_media_file(candidate, tmp_path)
    assert result["status"] == "blocked_or_unsupported"
    assert "ssrf" in result["reason"].lower() or "blocked" in result["reason"].lower()
    assert result["file_path"] is None


@pytest.mark.anyio
async def test_failed_download_handled_gracefully(tmp_path, monkeypatch):
    class FailingResponse:
        status_code = 404
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class FailingClient:
        def stream(self, method, url):
            return FailingResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: FailingClient())

    candidate = {
        "media_type": "reel",
        "is_reel": True,
        "video_url": "https://scontent.cdninstagram.com/missing.mp4",
        "post_url": "https://www.instagram.com/reel/missing/",
    }

    result = await retrieve_candidate_media_file(candidate, tmp_path)
    assert result["status"] == "failed"
    assert "404" in result["reason"]
    assert result["file_path"] is None


def test_end_to_end_discovery_in_investigation_and_pdf_report(tmp_path):
    # 1. Create Instagram seller case with relevant posts and an unauthenticated Reel
    payload = {
        "profile_url": "https://www.instagram.com/artisan_crafts/",
        "username": "artisan_crafts",
        "display_name": "Artisan Leather Crafts",
        "product_name": "Handmade Leather Wallet",
        "bio": "Genuine full grain leather wallets. DM to order. No refunds.",
        "website_url": "https://wa.me/1234567890",
        "followers": 300,
        "following": 1200,
        "post_count": 2,
        "posts": [
            {
                "url": "https://www.instagram.com/reel/demo_wallet/",
                "caption": "Watch our demonstration and water resistance test of the handmade leather wallet!",
                "timestamp": "2026-10-20",
                "is_reel": True,
                "media_type": "reel",
                "video_url": None,  # Will test graceful blocked probe handling
            },
            {
                "url": "https://www.instagram.com/p/photo_wallet/",
                "caption": "Handmade leather wallet close up stitching details.",
                "timestamp": "2026-10-21",
                "media_type": "image",
                "image_urls": [],
            },
        ],
    }

    create_res = client.post("/api/v1/instagram/inspect", json=payload)
    assert create_res.status_code == 201, create_res.text
    case_id = create_res.json()["case_id"]

    try:
        # 2. Run investigation (triggers automated media discovery)
        inv_res = client.post(
            f"/api/v1/cases/{case_id}/investigations",
            json={"check_linked_site": False, "check_public_complaints": False, "check_images": False, "auto_discover_media": True},
        )
        assert inv_res.status_code in {200, 202}, inv_res.text
        inv_data = inv_res.json()

        # Check discovered media output
        assert "discovered_media" in inv_data
        disc = inv_data["discovered_media"]
        assert disc is not None
        assert disc["candidates_ranked"] >= 1
        assert any(c["is_reel"] for c in disc["candidates"])

        # 3. Check case detail has discovered_media
        detail = client.get(f"/api/v1/cases/{case_id}").json()
        assert detail["discovered_media"] is not None
        assert detail["discovered_media"]["candidates_ranked"] >= 1

        # Check that the blocked Reel created an informational finding with explanation
        reel_findings = [f for f in detail["findings"] if f["category"] == "reel_retrieval_status"]
        assert len(reel_findings) >= 1
        assert "access controls" in reel_findings[0]["claim"].lower()
        assert reel_findings[0]["risk_weight"] == 0  # Deterministic score unchanged

        # 4. Generate report
        report_res = client.post(f"/api/v1/cases/{case_id}/report")
        assert report_res.status_code == 201, report_res.text
        download_url = report_res.json()["download_url"]

        # 5. Download and verify PDF
        pdf_res = client.get(download_url)
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF-")

    finally:
        # 6. Cleanup
        del_res = client.delete(f"/api/v1/cases/{case_id}")
        assert del_res.status_code == 204
