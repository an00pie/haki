import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.instagram_graph import InstagramGraphAdapter

@pytest.mark.anyio
async def test_instagram_graph_unconfigured():
    adapter = InstagramGraphAdapter(token="")
    assert not adapter.is_configured
    res = await adapter.fetch_account_and_media("test_user")
    assert res["status"] == "not_configured"
    assert res["profile"] is None
    assert "not configured" in res["reason"]

@pytest.mark.anyio
async def test_instagram_graph_success():
    adapter = InstagramGraphAdapter(token="EAABvalid_test_token")
    assert adapter.is_configured

    mock_profile_resp = httpx.Response(
        200,
        json={
            "id": "17841400000000001",
            "username": "verified_shop",
            "name": "Verified Shop Official",
            "biography": "Official store with verified buyer protection",
            "website": "https://verifiedshop.com",
            "followers_count": 15400,
            "follows_count": 120,
            "media_count": 85,
        },
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/verified_shop")
    )

    mock_media_resp = httpx.Response(
        200,
        json={
            "data": [
                {
                    "id": "media_123",
                    "caption": "New arrival sneakers in stock!",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/test123/",
                    "media_url": "https://cdn.instagram.com/media123.jpg",
                    "timestamp": "2026-10-20T10:00:00+0000",
                    "like_count": 450,
                    "comments_count": 32,
                }
            ]
        },
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/17841400000000001/media")
    )

    with patch("httpx.AsyncClient.get", side_effect=[mock_profile_resp, mock_media_resp]):
        res = await adapter.fetch_account_and_media("verified_shop")
        assert res["status"] == "completed"
        assert res["profile"]["username"] == "verified_shop"
        assert res["profile"]["followers"] == 15400
        assert len(res["media"]) == 1
        assert res["media"][0]["id"] == "media_123"

@pytest.mark.anyio
async def test_instagram_graph_expired_token():
    adapter = InstagramGraphAdapter(token="EAABexpired_token")
    mock_resp = httpx.Response(
        400,
        json={"error": {"code": 190, "error_subcode": 463, "message": "Session has expired"}},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/test")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await adapter.fetch_account_and_media("test_user")
        assert res["status"] == "expired_token"
        assert "expired" in res["reason"]

@pytest.mark.anyio
async def test_instagram_graph_permission_denied():
    adapter = InstagramGraphAdapter(token="EAABtoken")
    mock_resp = httpx.Response(
        403,
        json={"error": {"code": 10, "message": "Application does not have permission"}},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/test")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await adapter.fetch_account_and_media("test_user")
        assert res["status"] == "permission_denied"

@pytest.mark.anyio
async def test_instagram_graph_rate_limited():
    adapter = InstagramGraphAdapter(token="EAABtoken")
    mock_resp = httpx.Response(
        429,
        json={"error": {"code": 4, "message": "Application request limit reached"}},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/test")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await adapter.fetch_account_and_media("test_user")
        assert res["status"] == "rate_limited"

@pytest.mark.anyio
async def test_instagram_graph_unsupported_account():
    adapter = InstagramGraphAdapter(token="EAABtoken")
    mock_resp = httpx.Response(
        400,
        json={"error": {"code": 100, "message": "Cannot query personal profile without business upgrade"}},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/test")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await adapter.fetch_account_and_media("personal_user")
        assert res["status"] == "unsupported_account"
