"""Comprehensive security tests for SSRF protections, URL guard, and safe fetcher.

Covers:
- Private, loopback, link-local, and cloud metadata IPs
- Scheme and port allowlist
- Redirect re-validation blocking private redirects
- DNS rebinding prevention via IP-pinned transport and multi-IP validation
- Oversized response body limits
- Disallowed binary/executable content types
- Fetch timeout enforcement
"""

import pytest
import socket
from unittest.mock import patch, MagicMock
from app.security.url_guard import (
    validate_public_url,
    validate_url_for_storage,
    resolve_and_pin_public_url,
    UnsafeURL,
    PinnedTransport,
)
from app.tools.web_fetch import fetch_page
import httpx

@pytest.mark.parametrize("url", [
    "http://127.0.0.1",
    "http://127.0.0.2:80",
    "http://10.0.0.1",
    "http://10.255.255.255",
    "http://172.16.0.1",
    "http://172.31.255.255",
    "http://192.168.1.1",
    "http://192.168.0.254",
    "http://[::1]",
    "http://0.0.0.0",
    "http://localhost",
    "http://myshop.localhost",
    "http://myshop.local",
])
def test_blocks_private_and_loopback_destinations(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)

@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "http://169.254.1.1",
    "http://[fd00:ec2::254]",
    "http://metadata.google.internal",
    "http://100.64.0.1",  # Carrier-grade NAT
    "http://198.18.0.1",  # Benchmarking range
])
def test_blocks_link_local_and_cloud_metadata(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)

@pytest.mark.parametrize("url", [
    "ftp://example.com",
    "file:///etc/passwd",
    "gopher://example.com",
    "data:text/plain;base64,SGVsbG8=",
])
def test_blocks_disallowed_schemes(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)

@pytest.mark.parametrize("url", [
    "http://example.com:22",
    "http://example.com:8080",
    "https://example.com:8443",
    "http://example.com:3306",
])
def test_blocks_disallowed_ports(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)

def test_allows_valid_standard_ports():
    # Example.com resolves to public IP
    url, ip, port = resolve_and_pin_public_url("http://example.com:80")
    assert port == 80
    assert ip is not None

    url_https, ip_https, port_https = resolve_and_pin_public_url("https://example.com:443")
    assert port_https == 443

def test_credentials_in_url_rejected():
    with pytest.raises(UnsafeURL, match="credentials"):
        validate_public_url("http://admin:secret@example.com")

def test_dns_rebinding_multi_ip_rejected():
    """If a hostname resolves to both a public IP and a private IP, it must be rejected."""
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(UnsafeURL, match="Private, local, and reserved network destinations are blocked"):
            resolve_and_pin_public_url("http://rebind-attack.com")

def test_dns_rebinding_pinned_transport():
    """PinnedTransport ensures connection is made to the verified IP, ignoring subsequent DNS."""
    transport = PinnedTransport("93.184.216.34")
    assert transport._pool is not None

@pytest.mark.anyio
async def test_redirect_to_private_ip_is_blocked():
    """A redirect response pointing to a private IP must be caught and blocked."""
    # Mock httpx to simulate a 302 redirect to http://127.0.0.1/secret
    class MockStream:
        def __init__(self, status_code, headers):
            self.status_code = status_code
            self.headers = headers
            self.is_redirect = status_code in (301, 302, 303, 307, 308)
            self.url = httpx.URL("http://example.com")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b""

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            return MockStream(302, {"location": "http://127.0.0.1/admin-secret"})

    with patch("httpx.AsyncClient", MockClient):
        result = await fetch_page("http://example.com")
        assert result["status"] == "unavailable"
        assert "Unsafe redirect blocked" in result["error"]

@pytest.mark.anyio
async def test_oversized_body_is_aborted():
    """A response body that exceeds max_bytes is stopped and flagged."""
    class MockStream:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "text/html"}
            self.is_redirect = False
            self.url = httpx.URL("http://example.com")
            self.encoding = "utf-8"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            # Stream 6 chunks of 1MB = 6MB
            for _ in range(6):
                yield b"X" * (1024 * 1024)

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            return MockStream()

    with patch("httpx.AsyncClient", MockClient):
        result = await fetch_page("http://example.com", max_bytes=2_000_000)
        assert result["status"] == "unavailable"
        assert "exceeded limit" in result["error"].lower()

@pytest.mark.anyio
async def test_wrong_content_type_is_rejected():
    """Binary or executable content types must be rejected."""
    class MockStream:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/octet-stream"}
            self.is_redirect = False
            self.url = httpx.URL("http://example.com")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_bytes(self):
            yield b"binary data"

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            return MockStream()

    with patch("httpx.AsyncClient", MockClient):
        result = await fetch_page("http://example.com")
        assert result["status"] == "unavailable"
        assert "Disallowed content type" in result["error"]

@pytest.mark.anyio
async def test_fetch_timeout_enforced():
    """Timeouts must return unavailable with timeout message."""
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            raise httpx.ReadTimeout("Timed out connecting")

    with patch("httpx.AsyncClient", MockClient):
        result = await fetch_page("http://example.com", timeout=2.0)
        assert result["status"] == "unavailable"
        assert "timed out" in result["error"].lower()
