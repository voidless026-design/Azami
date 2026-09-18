"""Collector registry."""
from __future__ import annotations

from azami.osint.base import Collector
from azami.osint.collectors import (
    BreachCollector,
    CrtShCollector,
    DNSCollector,
    GeoIPCollector,
    RDAPCollector,
)

_REGISTRY: dict[str, Collector] = {}


def register(collector: Collector) -> None:
    _REGISTRY[collector.name] = collector


def all_collectors() -> list[Collector]:
    return list(_REGISTRY.values())


def applicable(kind: str, sources: list[str] | None = None) -> list[Collector]:
    out = []
    for c in _REGISTRY.values():
        if not c.enabled:
            continue
        if kind not in c.applies_to:
            continue
        if sources is not None and c.name not in sources:
            continue
        out.append(c)
    return out


def _bootstrap() -> None:
    for cls in (DNSCollector, RDAPCollector, CrtShCollector, GeoIPCollector, BreachCollector):
        register(cls())


_bootstrap()
