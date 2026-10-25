"""Safe page fetcher using IP-pinned transport, redirect re-validation, size, and timeout bounds."""

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.security.url_guard import (
    resolve_and_pin_public_url,
    PinnedTransport,
    UnsafeURL,
    OversizedBodyError,
    InvalidContentTypeError,
)
from app.config import settings

DISALLOWED_CONTENT_TYPES = (
    "application/octet-stream",
    "application/x-executable",
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/pdf",
    "video/",
    "audio/",
)

async def fetch_page(
    url: str,
    timeout: float | None = None,
    max_bytes: int | None = None,
) -> dict:
    """Safely fetch and parse a public web page with strict SSRF controls.

    - Resolves DNS once and pins connection to verified public IP.
    - Manually validates each redirect target against private/reserved IPs.
    - Caches no cookies and sends no authorization credentials.
    - Rejects binary/executable content types.
    - Aborts early if response body exceeds max_bytes.
    - Enforces strict execution timeout.
    """
    effective_timeout = timeout or settings.fetch_timeout_s
    effective_max_bytes = max_bytes or settings.fetch_max_bytes
    redirect_limit = 4

    try:
        current_url, pinned_ip, port = resolve_and_pin_public_url(url)
    except UnsafeURL as e:
        return {"status": "unavailable", "error": f"URL rejected: {e}", "url": url}

    initial_url = current_url
    redirect_chain = []
    headers = {
        "User-Agent": "ScamTrace-AI/1.0 (local user-requested check; non-crawler)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    for step in range(redirect_limit + 1):
        transport = PinnedTransport(pinned_ip)
        try:
            async with httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(effective_timeout),
                follow_redirects=False,
                headers=headers,
            ) as client:
                async with client.stream("GET", current_url) as response:
                    # 1. Manual redirect re-validation
                    if response.is_redirect:
                        loc = response.headers.get("location")
                        if not loc:
                            return {
                                "status": "unavailable",
                                "error": "Redirect response lacked Location header",
                                "url": current_url,
                            }
                        next_url_raw = urljoin(current_url, loc)
                        try:
                            next_url, next_pinned_ip, next_port = resolve_and_pin_public_url(next_url_raw)
                        except UnsafeURL as e:
                            return {
                                "status": "unavailable",
                                "error": f"Unsafe redirect blocked: {e}",
                                "url": current_url,
                            }

                        redirect_chain.append({
                            "from": current_url,
                            "to": next_url,
                            "status": response.status_code,
                        })
                        current_url = next_url
                        pinned_ip = next_pinned_ip
                        continue

                    # 2. Content-Type check
                    content_type = response.headers.get("content-type", "").lower()
                    if any(bad in content_type for bad in DISALLOWED_CONTENT_TYPES):
                        return {
                            "status": "unavailable",
                            "error": f"Disallowed content type: {content_type}",
                            "url": current_url,
                        }

                    # 3. HTTP status check
                    if response.status_code >= 400:
                        return {
                            "status": "unavailable",
                            "error": f"HTTP {response.status_code}",
                            "url": current_url,
                        }

                    # 4. Body size streaming check
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > effective_max_bytes:
                            return {
                                "status": "unavailable",
                                "error": f"Response body exceeded limit of {effective_max_bytes} bytes",
                                "url": current_url,
                            }

                    page_url = str(response.url)
                    http_status = response.status_code
                    encoding = response.encoding or "utf-8"

            # Parse HTML content
            soup = BeautifulSoup(bytes(body).decode(encoding, errors="replace"), "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            text = soup.get_text(" ", strip=True)[:2000]

            image_urls = []
            for node in soup.select('meta[property="og:image"], img[src]'):
                raw = node.get("content") or node.get("src")
                if not raw:
                    continue
                candidate = urljoin(page_url, raw)
                if candidate.startswith(("http://", "https://")) and candidate not in image_urls:
                    image_urls.append(candidate)
                if len(image_urls) >= 12:
                    break

            return {
                "status": "completed",
                "requested_url": initial_url,
                "url": page_url,
                "http_status": http_status,
                "https_final": page_url.lower().startswith("https://"),
                "redirect_chain": redirect_chain,
                "title": title[:300],
                "text_excerpt": text,
                "image_urls": image_urls,
            }

        except httpx.TimeoutException:
            return {
                "status": "unavailable",
                "error": f"Request timed out after {effective_timeout}s",
                "url": current_url,
            }
        except httpx.HTTPError as e:
            return {
                "status": "unavailable",
                "error": str(e)[:300],
                "url": current_url,
            }
        except UnsafeURL as e:
            return {
                "status": "unavailable",
                "error": f"Security check failed: {e}",
                "url": current_url,
            }

    return {"status": "unavailable", "error": "Redirect limit exceeded", "url": current_url}
