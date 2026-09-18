"""Job service: submit (gated) -> queue -> run -> stream -> persist, with cancellation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.audit.log import AuditLogger
from azami.config import get_settings
from azami.engagement import manager
from azami.jobs.events import bus
from azami.persistence.db import SessionLocal
from azami.persistence.models import Finding, Job
from azami.runners.base import JobEvent, JobState, ToolPlan, ToolUnavailable
from azami.runners.manager import get_runner
from azami.scope.schema import INTRUSIVE_ACTIONS
from azami.tools import registry as tool_registry

log = logging.getLogger("azami.jobs")


class IntrusiveConfirmationRequired(Exception):
    def __init__(self, tool: str, action: str):
        self.tool = tool
        self.action = action
        super().__init__(f"tool '{tool}' requires confirmation for intrusive action '{action}'")


class UnknownTool(Exception):
    pass


def _result_hash(result: dict) -> str:
    return hashlib.sha256(
        json.dumps(result, sort_keys=True, default=str).encode()
    ).hexdigest()


class JobService:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._sem: asyncio.Semaphore | None = None
        self._sem_loop: asyncio.AbstractEventLoop | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        # Bind the semaphore to the running loop; recreate if the loop changed
        # (production has one loop; tests spin up a fresh loop per test).
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem_loop is not loop:
            self._sem = asyncio.Semaphore(get_settings().max_global_concurrency)
            self._sem_loop = loop
        return self._sem

    def submit(
        self,
        db: Session,
        *,
        tool: str,
        target: str,
        params: dict,
        operator_id: str | None,
        confirm_intrusive: bool = False,
    ) -> Job:
        wrapper = tool_registry.get(tool)
        if wrapper is None:
            raise UnknownTool(tool)

        # Intrusive actions need explicit per-run confirmation BEFORE we gate/run.
        if wrapper.required_action in INTRUSIVE_ACTIONS and not confirm_intrusive:
            raise IntrusiveConfirmationRequired(tool, wrapper.required_action.value)

        # Build + validate the plan (raises ToolParamError on bad params).
        constraints = {}
        engine = manager.get_engine()
        if engine is not None:
            constraints = engine.scope.constraints.model_dump()
        plan = wrapper.plan(target, params, constraints)

        # Scope gate (audited). Raises NoActiveEngagement / ScopeDenied.
        manager.gate(
            db,
            target=target,
            action=wrapper.required_action,
            label=f"run:{tool}",
            operator_id=operator_id,
            tool=tool,
            params=params,
        )

        job = Job(
            engagement_id=manager.active_engagement_id,
            operator_id=operator_id,
            tool=tool,
            target=target,
            params=params,
            state=JobState.QUEUED.value,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        self._tasks[job.id] = asyncio.create_task(self._execute(job.id, plan))
        return job

    async def await_job(self, job_id: str) -> None:
        task = self._tasks.get(job_id)
        if task:
            await asyncio.gather(task, return_exceptions=True)

    async def _execute(self, job_id: str, plan: ToolPlan) -> None:
        db = SessionLocal()
        try:
            async with self._semaphore():
                await self._run_once(db, job_id, plan)
        finally:
            db.close()
            self._tasks.pop(job_id, None)

    async def _run_once(self, db: Session, job_id: str, plan: ToolPlan) -> None:
        job = db.get(Job, job_id)
        if job is None or job.state != JobState.QUEUED.value:
            return  # cancelled before it started

        wrapper = tool_registry.get(job.tool)
        self._set_state(db, job, JobState.RUNNING, started=True)

        def on_event(kind: str, text: str) -> None:
            bus.publish(job_id, JobEvent(job_id, kind, text).to_dict())

        try:
            result = await get_runner().run(plan, on_event)
        except asyncio.CancelledError:
            self._finish(db, job, JobState.CANCELLED, error="cancelled")
            raise
        except asyncio.TimeoutError:
            self._finish(db, job, JobState.TIMED_OUT, error="timed out")
            return
        except ToolUnavailable as exc:
            self._finish(db, job, JobState.FAILED, error=str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("job %s crashed", job_id)
            self._finish(db, job, JobState.FAILED, error=str(exc))
            return

        parsed, findings = wrapper.parse(result.stdout, result.stderr, result.exit_code)
        job.stdout = result.stdout
        job.stderr = result.stderr
        job.exit_code = result.exit_code
        job.result = parsed
        job.result_hash = _result_hash(parsed)
        for f in findings:
            db.add(
                Finding(
                    engagement_id=job.engagement_id,
                    job_id=job.id,
                    title=f.get("title", "finding"),
                    severity=f.get("severity", "info"),
                    description=f.get("description", ""),
                    evidence=f.get("evidence", {}),
                )
            )
        state = JobState.SUCCEEDED if result.exit_code == 0 else JobState.FAILED
        self._finish(db, job, state, result_hash=job.result_hash)

    # -- state helpers -------------------------------------------------------
    def _set_state(self, db: Session, job: Job, state: JobState, *, started: bool = False) -> None:
        job.state = state.value
        if started:
            job.started_at = datetime.now(timezone.utc)
        db.commit()
        bus.publish(job.id, JobEvent(job.id, "state", state.value).to_dict())

    def _finish(
        self, db: Session, job: Job, state: JobState, *, error: str | None = None,
        result_hash: str | None = None,
    ) -> None:
        job.state = state.value
        job.finished_at = datetime.now(timezone.utc)
        if error:
            job.error = error
        db.commit()
        bus.publish(job.id, JobEvent(job.id, "state", state.value).to_dict())
        AuditLogger(db).record(
            action=f"job.finished:{job.tool}",
            engagement_id=job.engagement_id,
            operator_id=job.operator_id,
            target=job.target,
            tool=job.tool,
            scope_decision=f"state={state.value}",
            result_hash=result_hash,
        )

    # -- cancellation --------------------------------------------------------
    def cancel(self, db: Session, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        job = db.get(Job, job_id)
        if job and job.state in (JobState.QUEUED.value, JobState.RUNNING.value):
            if task:
                task.cancel()
            else:  # no running task (e.g. after restart): mark cancelled directly
                self._finish(db, job, JobState.CANCELLED, error="cancelled")
            return True
        return False

    def cancel_all(self, db: Session, engagement_id: str) -> int:
        rows = db.execute(
            select(Job).where(
                Job.engagement_id == engagement_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
            )
        ).scalars().all()
        count = 0
        for job in rows:
            if self.cancel(db, job.id):
                count += 1
        return count


job_service = JobService()
