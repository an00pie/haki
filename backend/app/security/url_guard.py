"""SSRF-safe URL validation and IP-pinned network transport.

Implements ScamTrace AI Phase 1 specifications:
- Scheme allowlist: http, https
- Port allowlist: 80, 443
- Credentials prohibited (user:pass@host)
- Rejection of localhost, .local, and .localhost
- Strict rejection of loopback, private, link-local, multicast, carrier-grade NAT, and cloud metadata IPs
- IP-pinned connection transport to completely eliminate DNS rebinding attacks
"""

import ipaddress
import socket
import ssl
from typing import Any, Iterable
from urllib.parse import urlparse, urljoin
import httpx
import httpcore
from httpcore._backends.anyio import AnyIOBackend

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}

# Cloud metadata addresses to explicitly guard against
METADATA_IPS = {
    "169.254.169.254",  # AWS / Azure / GCP metadata IPv4
    "fd00:ec2::254",    # AWS metadata IPv6
    "metadata.google.internal",
}

class UnsafeURL(ValueError):
    """Raised when a URL targets a private, reserved, or prohibited destination."""
    pass

class OversizedBodyError(ValueError):
    """Raised when an HTTP response body exceeds size limits."""
    pass

class InvalidContentTypeError(ValueError):
    """Raised when an HTTP response content-type is disallowed."""
    pass

def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False

def is_ip_safe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP is globally routable and not private/loopback/link-local/metadata."""
    # Direct check against known metadata literals
    if str(ip) in METADATA_IPS:
        return False

    # Block loopback, private, link-local, multicast, reserved, unspecified
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False

    # Carrier-grade NAT (100.64.0.0/10)
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.IPv4Network("100.64.0.0/10"):
        return False

    # IPv4 Benchmarking / Test / Documentation
    if isinstance(ip, ipaddress.IPv4Address) and (
        ip in ipaddress.IPv4Network("198.18.0.0/15")
        or ip in ipaddress.IPv4Network("192.0.2.0/24")
        or ip in ipaddress.IPv4Network("198.51.100.0/24")
        or ip in ipaddress.IPv4Network("203.0.113.0/24")
    ):
        return False

    # Must be global
    return ip.is_global

def resolve_and_pin_public_url(url: str) -> tuple[str, str, int]:
    """Validate URL syntax, scheme, port, credentials, and DNS records.

    Resolves DNS once and returns (normalized_url, pinned_ip, port).
    All resolved IP addresses are verified. If any is private or unsafe, raises UnsafeURL.
    """
    p = urlparse(url)
    scheme = p.scheme.lower() if p.scheme else ""
    if scheme not in ALLOWED_SCHEMES or not p.hostname:
        raise UnsafeURL("Only valid HTTP(S) URLs are allowed")

    if p.username or p.password:
        raise UnsafeURL("URLs containing credentials are not allowed")

    # Port allowlist
    port = p.port
    if port is None:
        port = 443 if scheme == "https" else 80
    elif port not in ALLOWED_PORTS:
        raise UnsafeURL(f"Port {port} is not allowed (only 80 and 443 are permitted)")

    host = p.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local") or host in METADATA_IPS:
        raise UnsafeURL("Local network and metadata destinations are blocked")

    try:
        if _is_ip(host):
            ip_obj = ipaddress.ip_address(host)
            addresses = [ip_obj]
        else:
            addr_info = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = [ipaddress.ip_address(item[4][0]) for item in addr_info]
    except (OSError, ValueError):
        raise UnsafeURL("Host could not be resolved safely")

    if not addresses:
        raise UnsafeURL("Host has no public address")

    # If ANY resolved address is private/reserved, reject to prevent DNS rebinding
    for addr in addresses:
        if not is_ip_safe(addr):
            raise UnsafeURL("Private, local, and reserved network destinations are blocked")

    pinned_ip = str(addresses[0])
    return url, pinned_ip, port

def validate_public_url(url: str) -> str:
    """Validate that a URL is public and safe to access."""
    norm_url, _, _ = resolve_and_pin_public_url(url)
    return norm_url

def validate_redirect(base: str, location: str) -> str:
    """Validate a redirect target relative to the base URL."""
    target = urljoin(base, location)
    return validate_public_url(target)

def validate_url_for_storage(url: str) -> str:
    """Validate syntax, scheme, port, and obvious IP targets without requiring live DNS.

    Used when recording user-provided URLs that may be offline.
    """
    p = urlparse(url)
    scheme = p.scheme.lower() if p.scheme else ""
    if scheme not in ALLOWED_SCHEMES or not p.hostname:
        raise UnsafeURL("Only valid HTTP(S) URLs are allowed")
    if p.username or p.password:
        raise UnsafeURL("URLs containing credentials are not allowed")

    port = p.port
    if port is not None and port not in ALLOWED_PORTS:
        raise UnsafeURL(f"Port {port} is not allowed (only 80 and 443 are permitted)")

    host = p.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local") or host in METADATA_IPS:
        raise UnsafeURL("Local network and metadata destinations are blocked")

    if _is_ip(host):
        ip_obj = ipaddress.ip_address(host)
        if not is_ip_safe(ip_obj):
            raise UnsafeURL("Private, local, and reserved network destinations are blocked")

    return url

class PinnedBackend(AnyIOBackend):
    """Network backend that connects directly to a pre-validated IP address.

    Preserves the SNI hostname and HTTP Host header while ensuring TCP connects
    strictly to the verified IP, preventing DNS rebinding attacks.
    """
    def __init__(self, pinned_ip: str):
        super().__init__()
        self.pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ):
        # Override remote_host with the pinned IP
        return await super().connect_tcp(
            remote_host=self.pinned_ip,
            remote_port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

class PinnedTransport(httpx.AsyncHTTPTransport):
    """HTTPX Async Transport pinned to a specific IP address to defeat DNS rebinding."""
    def __init__(self, pinned_ip: str, **kwargs: Any):
        super().__init__(**kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            network_backend=PinnedBackend(pinned_ip),
            http1=True,
            http2=False,
        )
