"""Meta / Instagram Graph API backend adapter for permitted account and media data.

Security & Architecture Principles:
- Access tokens reside strictly on the backend and are read from environment variables.
- Never exposed in frontend bundles, logs, or API responses.
- Respects granted permissions, account eligibility (business/creator accounts), and API rate limits.
- Gracefully handles expired tokens, denied permissions, unsupported accounts, and rate limiting.
- Does not bypass login restrictions, defeat CAPTCHAs, or call unauthorized endpoints.
- Seamlessly falls back to visible-page extraction or user-supplied manual inputs.
"""

from __future__ import annotations
import logging
from typing import Any
import httpx
from app.config import settings
from app.security.url_guard import validate_public_url, UnsafeURL

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class InstagramGraphAdapter:
    def __init__(self, token: str | None = None):
        self.token = token or getattr(settings, "instagram_api_token", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.token.strip())

    async def fetch_account_and_media(self, ig_user_id_or_username: str) -> dict[str, Any]:
        """Fetch permitted account and media data from Meta Graph API.
        
        Returns a standardized dictionary with status:
        - "completed": account and media successfully fetched
        - "not_configured": no token provided (prompts fallback)
        - "expired_token": token has expired
        - "permission_denied": token lacks necessary permissions
        - "rate_limited": Graph API rate limit reached
        - "unsupported_account": personal account or not accessible
        - "unavailable": network or server error
        """
        if not self.is_configured:
            return {
                "status": "not_configured",
                "reason": "INSTAGRAM_API_TOKEN is not configured on the backend.",
                "profile": None,
                "media": [],
            }

        target = ig_user_id_or_username.strip().lstrip("@")
        if not target:
            return {
                "status": "unavailable",
                "reason": "Missing Instagram account identifier.",
                "profile": None,
                "media": [],
            }

        endpoint = f"{GRAPH_BASE_URL}/{target}"
        params = {
            "fields": "id,username,name,biography,website,followers_count,follows_count,media_count,profile_picture_url",
            "access_token": self.token,
        }

        try:
            validate_public_url(endpoint)
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False, trust_env=False) as client:
                res = await client.get(endpoint, params=params)

                if res.status_code == 200:
                    profile_data = res.json()
                    media_data = await self._fetch_media(client, profile_data.get("id") or target)
                    return {
                        "status": "completed",
                        "profile": {
                            "username": profile_data.get("username", target),
                            "display_name": profile_data.get("name"),
                            "bio": profile_data.get("biography"),
                            "website_url": profile_data.get("website"),
                            "followers": profile_data.get("followers_count"),
                            "following": profile_data.get("follows_count"),
                            "post_count": profile_data.get("media_count"),
                            "profile_url": f"https://www.instagram.com/{profile_data.get('username', target)}/",
                        },
                        "media": media_data,
                    }

                # Handle Graph API specific error payloads
                error_payload = {}
                try:
                    error_payload = res.json().get("error", {})
                except Exception:
                    pass

                code = error_payload.get("code")
                error_subcode = error_payload.get("error_subcode")
                msg = error_payload.get("message", f"HTTP {res.status_code}")

                if code == 190 or error_subcode in {463, 467}:
                    return {
                        "status": "expired_token",
                        "reason": f"Instagram access token is expired or invalidated: {msg}",
                        "profile": None,
                        "media": [],
                    }
                elif code in {10, 200, 210}:
                    return {
                        "status": "permission_denied",
                        "reason": f"Permission denied for Instagram Graph query: {msg}",
                        "profile": None,
                        "media": [],
                    }
                elif code in {4, 17, 32, 613}:
                    return {
                        "status": "rate_limited",
                        "reason": f"Instagram Graph API rate limit exceeded: {msg}",
                        "profile": None,
                        "media": [],
                    }
                elif code in {100, 803}:
                    return {
                        "status": "unsupported_account",
                        "reason": f"Account is not an eligible Instagram Business/Creator account or is unavailable: {msg}",
                        "profile": None,
                        "media": [],
                    }
                else:
                    return {
                        "status": "unavailable",
                        "reason": f"Meta Graph API error (code {code}): {msg}",
                        "profile": None,
                        "media": [],
                    }

        except UnsafeURL as e:
            return {
                "status": "unavailable",
                "reason": f"Security policy blocked target URL: {e}",
                "profile": None,
                "media": [],
            }
        except Exception as e:
            logger.warning(f"Error querying Instagram Graph API: {e}")
            return {
                "status": "unavailable",
                "reason": f"Graph network request error: {str(e)[:200]}",
                "profile": None,
                "media": [],
            }

    async def _fetch_media(self, client: httpx.AsyncClient, ig_user_id: str) -> list[dict[str, Any]]:
        """Fetch permitted recent posts/reels for the business account."""
        media_endpoint = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
            "limit": "8",
            "access_token": self.token,
        }
        try:
            res = await client.get(media_endpoint, params=params)
            if res.status_code != 200:
                return []
            items = res.json().get("data", [])
            media = []
            for item in items:
                media.append({
                    "id": item.get("id"),
                    "caption": item.get("caption"),
                    "media_type": item.get("media_type"),
                    "url": item.get("permalink"),
                    "media_url": item.get("media_url"),
                    "timestamp": item.get("timestamp"),
                    "likes": item.get("like_count"),
                    "comments_count": item.get("comments_count"),
                })
            return media
        except Exception as e:
            logger.warning(f"Error fetching Instagram media: {e}")
            return []

instagram_graph_adapter = InstagramGraphAdapter()
