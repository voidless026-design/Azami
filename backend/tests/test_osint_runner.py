"""OSINT runner: scope-gated, offline via a stub collector."""
from __future__ import annotations

import pytest

from azami.engagement import ScopeDenied, manager
from azami.entities import service
from azami.entities.canonical import EntityType
from azami.osint import registry
from azami.osint.base import Collector, RawRecord
from azami.osint.runner import classify, run_collectors

SCOPE = """
schema_version: 1
engagement: {id: ENG-OSINT, client_name: C, assessing_org: F, authorization_ref: S}
time_window: {not_before: "2020-01-01T00:00:00Z", not_after: "2035-12-31T23:59:59Z"}
in_scope:
  - name: web
    domains: ["example.com", "*.example.com"]
    allowed_actions: {passive: true}
out_of_scope: {hosts: ["secret.example.com"]}
"""


class StubCollector(Collector):
    name = "stub"
    produces = [EntityType.HOST]
    applies_to = {"domain"}

    async def collect(self, value, kind):
        return [RawRecord(EntityType.HOST, f"sub.{value}", {"host": f"sub.{value}"})]


@pytest.fixture
def engagement(db):
    registry.register(StubCollector())
    manager.load(db, scope_text=SCOPE, operator_id=None)
    yield
    manager._engine = None
    manager._engagement_id = None


def test_classify():
    assert classify("alice@example.com") == ("email", "alice@example.com", "example.com")
    assert classify("203.0.113.10")[0] == "ip"
    assert classify("HTTPS://API.Example.com")[:2] == ("domain", "api.example.com")


async def test_collect_in_scope_persists_entities(db, engagement):
    result = await run_collectors(db, target="api.example.com", operator_id=None, sources=["stub"])
    assert result["kind"] == "domain"
    assert any(c["collector"] == "stub" and c["count"] == 1 for c in result["collectors"])
    ents = service.list_entities(db, manager.active_engagement_id)
    keys = {e.dedup_key for e in ents}
    assert "api.example.com" in keys and "sub.api.example.com" in keys


async def test_collect_out_of_scope_denied(db, engagement):
    with pytest.raises(ScopeDenied):
        await run_collectors(db, target="secret.example.com", operator_id=None, sources=["stub"])


async def test_collect_not_in_scope_denied(db, engagement):
    with pytest.raises(ScopeDenied):
        await run_collectors(db, target="evil.org", operator_id=None, sources=["stub"])
