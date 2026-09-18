"""Confidence scoring: source reliability weights + corroboration boost.

Answers "if the input is ambiguous, how do we rank matches": each asserted fact carries a
source-reliability weight; independent sources agreeing raise confidence multiplicatively
toward 1.0. Candidate identities are ranked by aggregate confidence, never silently merged.
"""
from __future__ import annotations

# Source reliability weights (0..1). Official/registry data outranks scraped/social.
SOURCE_WEIGHTS = {
    "rdap": 0.9,
    "whois": 0.85,
    "dns": 0.85,
    "crtsh": 0.8,
    "asn": 0.85,
    "public_record": 0.9,
    "geoip": 0.6,
    "breach": 0.7,
    "scrape": 0.4,
    "social": 0.3,
    # tools
    "nmap": 0.9,
    "gobuster": 0.8,
}
DEFAULT_WEIGHT = 0.5


def source_weight(source: str) -> float:
    return SOURCE_WEIGHTS.get(source, DEFAULT_WEIGHT)


def corroborate(existing: float, new_weight: float) -> float:
    """Combine an existing confidence with a new corroborating source toward 1.0."""
    existing = max(0.0, min(1.0, existing))
    new_weight = max(0.0, min(1.0, new_weight))
    return round(1.0 - (1.0 - existing) * (1.0 - new_weight), 4)
