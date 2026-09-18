"""Canonicalize a target string into a typed, comparable form.

Every scope decision runs the raw operator/collector input through here first so that
`HTTPS://Example.com/`, `example.com`, and a resolved IP are judged consistently and a
near-miss cannot slip past the gate.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import tldextract

# Use the bundled public-suffix snapshot; do not fetch at runtime.
_extract = tldextract.TLDExtract(suffix_list_urls=())


class TargetKind(str, Enum):
    IP = "ip"
    DOMAIN = "domain"


@dataclass(frozen=True)
class CanonicalTarget:
    kind: TargetKind
    value: str  # canonical ip string, or canonical (lowercased, idna) hostname
    registrable_domain: str | None = None  # e.g. example.com for a.example.com
    raw: str = ""


def _try_ip(text: str) -> str | None:
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def _normalize_host(host: str) -> str:
    host = host.strip().rstrip(".").lower()
    try:
        # IDNA/punycode-normalize; ignore failures and keep the lowercased form.
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        pass
    return host


def canonicalize(target: str) -> CanonicalTarget:
    raw = target
    text = target.strip()

    # A bare IP?
    ip = _try_ip(text)
    if ip is not None:
        return CanonicalTarget(TargetKind.IP, ip, raw=raw)

    # A URL? Extract the host (and possibly an IP host).
    if "://" in text or text.startswith("//"):
        parsed = urlparse(text if "://" in text else f"http:{text}")
        host = parsed.hostname or ""
    else:
        # Could be "host:port" or "host/path"; strip both.
        host = text.split("/", 1)[0].split(":", 1)[0]

    ip = _try_ip(host)
    if ip is not None:
        return CanonicalTarget(TargetKind.IP, ip, raw=raw)

    host = _normalize_host(host)
    ext = _extract(host)
    registrable = ".".join(p for p in (ext.domain, ext.suffix) if p) or None
    return CanonicalTarget(TargetKind.DOMAIN, host, registrable_domain=registrable, raw=raw)


def domain_matches(pattern: str, host: str) -> bool:
    """Match a host against a scope pattern.

    - "example.com"   matches only example.com (exact).
    - "*.example.com" matches any subdomain (a.example.com, a.b.example.com) but NOT example.com.
    """
    pattern = _normalize_host(pattern)
    host = _normalize_host(host)
    if pattern.startswith("*."):
        base = pattern[2:]
        return host.endswith("." + base)
    return host == pattern


def ip_in_range(ip: str, cidr: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False
