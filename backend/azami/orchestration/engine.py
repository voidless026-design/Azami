"""Playbook engine: run steps in order, fan out over discovered entities, re-gate every target."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from azami.engagement import NoActiveEngagement, ScopeDenied, manager
from azami.entities import service as entity_service
from azami.jobs.service import IntrusiveConfirmationRequired, job_service
from azami.orchestration.playbook import Playbook, PlaybookStep
from azami.osint.runner import run_collectors
from azami.persistence.models import Job

log = logging.getLogger("azami.playbook")


def _resolve_targets(db: Session, step: PlaybookStep, root_target: str) -> list[str]:
    if step.targets == "root":
        return [root_target]
    eid = manager.active_engagement_id
    if step.targets == "ips":
        return [e.dedup_key for e in entity_service.list_entities(db, eid, "ip")]
    if step.targets == "hosts":
        hosts = entity_service.list_entities(db, eid, "host")
        domains = entity_service.list_entities(db, eid, "domain")
        return [e.dedup_key for e in (*hosts, *domains)]
    return [root_target]


async def run_playbook(
    db: Session, *, playbook: Playbook, root_target: str, operator_id: str | None
) -> dict:
    if manager.is_locked():
        raise NoActiveEngagement("no active engagement; load a scope first")

    steps_out: list[dict] = []
    for step in playbook.steps:
        targets = _resolve_targets(db, step, root_target)
        runs: list[dict] = []
        for target in targets:
            try:
                if step.action == "collect":
                    r = await run_collectors(
                        db, target=target, operator_id=operator_id, sources=[step.name]
                    )
                    runs.append({"target": target, "ok": True, "result": r})
                else:
                    job = job_service.submit(
                        db,
                        tool=step.name,
                        target=target,
                        params=step.params,
                        operator_id=operator_id,
                        confirm_intrusive=step.params.get("confirm_intrusive", False),
                    )
                    await job_service.await_job(job.id)
                    db.expire_all()
                    j = db.get(Job, job.id)
                    runs.append(
                        {"target": target, "ok": True, "job_id": job.id, "state": j.state}
                    )
            except ScopeDenied as exc:
                runs.append({"target": target, "ok": False, "skipped": exc.decision.reason})
            except IntrusiveConfirmationRequired as exc:
                runs.append({"target": target, "ok": False, "skipped": str(exc)})
            except Exception as exc:  # keep the playbook going; record the failure
                log.warning("step %s failed on %s: %s", step.id, target, exc)
                runs.append({"target": target, "ok": False, "error": str(exc)})
        steps_out.append(
            {"step": step.id, "action": step.action, "name": step.name, "runs": runs}
        )

    return {"playbook": playbook.name, "root": root_target, "steps": steps_out}
