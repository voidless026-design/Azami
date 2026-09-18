"""Playbook cascading + per-derived-target re-gating, and report building."""
from __future__ import annotations

import pytest

from azami.engagement import manager
from azami.entities.canonical import EntityType
from azami.orchestration.engine import run_playbook
from azami.orchestration.playbook import Playbook, PlaybookStep
from azami.osint import registry as osint_registry
from azami.osint.base import Collector, RawRecord
from azami.report import service as report_service
from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools import registry as tool_registry
from azami.tools.base import ToolWrapper

SCOPE = """
schema_version: 1
engagement: {id: ENG-PB, client_name: C, assessing_org: F, authorization_ref: S}
time_window: {not_before: "2020-01-01T00:00:00Z", not_after: "2035-12-31T23:59:59Z"}
in_scope:
  - name: web
    domains: ["example.com", "*.example.com"]
    allowed_actions: {passive: true, active_scan: true}
  - name: net
    ip_ranges: ["203.0.113.0/24"]
    allowed_actions: {passive: true, active_scan: true}
"""


class MultiIPCollector(Collector):
    name = "stub_ips"
    produces = [EntityType.IP]
    applies_to = {"domain"}

    async def collect(self, value, kind):
        # One in-scope IP and one out-of-scope IP (8.8.8.8) to prove re-gating.
        return [
            RawRecord(EntityType.IP, "203.0.113.10", {"ip": "203.0.113.10"}),
            RawRecord(EntityType.IP, "8.8.8.8", {"ip": "8.8.8.8"}),
        ]


class FakePortScan(ToolWrapper):
    name = "fakescan2"
    required_action = Action.ACTIVE_SCAN

    def plan(self, target, params, constraints):
        return ToolPlan(
            tool=self.name, target=target, argv=["printf", "ok\\n"],
            required_action=self.required_action, timeout=30,
        )

    def parse(self, stdout, stderr, exit_code):
        return {"lines": len(stdout.splitlines())}, []


@pytest.fixture
def engagement(db):
    osint_registry.register(MultiIPCollector())
    tool_registry.register(FakePortScan())
    manager.load(db, scope_text=SCOPE, operator_id=None)
    yield
    manager._engine = None
    manager._engagement_id = None


PLAYBOOK = Playbook(
    name="test_pb",
    description="stub collect -> fanout scan over discovered IPs",
    steps=[
        PlaybookStep("discover", "collect", "stub_ips", "root"),
        PlaybookStep("scan", "tool", "fakescan2", "ips"),
    ],
)


async def test_playbook_fanout_regates_derived_targets(db, engagement):
    result = await run_playbook(
        db, playbook=PLAYBOOK, root_target="example.com", operator_id=None
    )
    scan_step = next(s for s in result["steps"] if s["step"] == "scan")
    by_target = {r["target"]: r for r in scan_step["runs"]}

    # In-scope IP was scanned; out-of-scope IP was re-gated and skipped.
    assert by_target["203.0.113.10"]["ok"] and by_target["203.0.113.10"]["state"] == "succeeded"
    assert by_target["8.8.8.8"]["ok"] is False and "skipped" in by_target["8.8.8.8"]


async def test_report_after_playbook(db, engagement):
    await run_playbook(db, playbook=PLAYBOOK, root_target="example.com", operator_id=None)
    report = report_service.build_report(db, manager.active_engagement_id)
    assert report["entities_total"] >= 2
    assert report["jobs_by_tool"].get("fakescan2", 0) >= 1
    assert report["audit"]["ok"] is True
    md = report_service.to_markdown(report)
    assert "Engagement Report" in md and "Audit trail integrity" in md
