"""Job lifecycle: gated submit, real subprocess execution, intrusive confirmation, cancel."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from azami.engagement import ScopeDenied, manager
from azami.jobs.service import IntrusiveConfirmationRequired, job_service
from azami.persistence.models import Finding, Job
from azami.runners.base import JobState, ToolPlan
from azami.scope.schema import Action
from azami.tools import registry as tool_registry
from azami.tools.base import ToolWrapper

SCOPE = """
schema_version: 1
engagement: {id: ENG-JOB, client_name: C, assessing_org: F, authorization_ref: S}
time_window: {not_before: "2020-01-01T00:00:00Z", not_after: "2035-12-31T23:59:59Z"}
in_scope:
  - name: web
    domains: ["example.com", "*.example.com"]
    allowed_actions: {passive: true, active_scan: true, active_testing: true}
out_of_scope: {hosts: ["secret.example.com"]}
"""


class FakeScan(ToolWrapper):
    name = "fakescan"
    required_action = Action.ACTIVE_SCAN

    def plan(self, target, params, constraints):
        return ToolPlan(
            tool=self.name, target=target, argv=["printf", "l1\\nl2\\n"],
            required_action=self.required_action, timeout=30,
        )

    def parse(self, stdout, stderr, exit_code):
        lines = [ln for ln in stdout.splitlines() if ln]
        return {"lines": len(lines)}, [
            {"title": "t", "severity": "info", "description": "d", "evidence": {}}
        ]


class FakeIntrusive(FakeScan):
    name = "fakeintr"
    required_action = Action.ACTIVE_TESTING


class MissingBinary(FakeScan):
    name = "missingbin"

    def plan(self, target, params, constraints):
        return ToolPlan(
            tool=self.name, target=target, argv=["azami-nonexistent-binary-xyz"],
            required_action=self.required_action, timeout=30,
        )


@pytest.fixture
def engagement(db):
    for cls in (FakeScan, FakeIntrusive, MissingBinary):
        tool_registry.register(cls())
    manager.load(db, scope_text=SCOPE, operator_id=None)
    yield
    manager._engine = None
    manager._engagement_id = None


async def test_job_success(db, engagement):
    job = job_service.submit(
        db, tool="fakescan", target="api.example.com", params={}, operator_id=None
    )
    assert job.state == JobState.QUEUED.value
    await job_service.await_job(job.id)

    db.expire_all()
    done = db.get(Job, job.id)
    assert done.state == JobState.SUCCEEDED.value
    assert done.exit_code == 0
    assert done.result["lines"] == 2
    assert "l1" in done.stdout
    findings = db.execute(select(Finding).where(Finding.job_id == job.id)).scalars().all()
    assert len(findings) == 1


async def test_intrusive_requires_confirmation(db, engagement):
    with pytest.raises(IntrusiveConfirmationRequired):
        job_service.submit(
            db, tool="fakeintr", target="example.com", params={}, operator_id=None
        )


async def test_intrusive_runs_with_confirmation(db, engagement):
    job = job_service.submit(
        db, tool="fakeintr", target="example.com", params={},
        operator_id=None, confirm_intrusive=True,
    )
    await job_service.await_job(job.id)
    db.expire_all()
    assert db.get(Job, job.id).state == JobState.SUCCEEDED.value


async def test_out_of_scope_denied(db, engagement):
    with pytest.raises(ScopeDenied):
        job_service.submit(
            db, tool="fakescan", target="secret.example.com", params={}, operator_id=None
        )


async def test_tool_unavailable_marks_failed(db, engagement):
    job = job_service.submit(
        db, tool="missingbin", target="example.com", params={}, operator_id=None
    )
    await job_service.await_job(job.id)
    db.expire_all()
    done = db.get(Job, job.id)
    assert done.state == JobState.FAILED.value
    assert "not installed" in (done.error or "")
