"""Job/tool endpoints: list tools, submit (gated), list/get/cancel jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.api.schemas import JobOut, JobSubmitRequest
from azami.auth.deps import get_current_operator, require_role
from azami.engagement import NoActiveEngagement, ScopeDenied
from azami.jobs.service import (
    IntrusiveConfirmationRequired,
    UnknownTool,
    job_service,
)
from azami.persistence.db import get_db
from azami.persistence.models import Job, Operator
from azami.scope.schema import INTRUSIVE_ACTIONS
from azami.tools import registry as tool_registry

router = APIRouter(prefix="/api", tags=["jobs"])


def _to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        engagement_id=job.engagement_id,
        tool=job.tool,
        target=job.target,
        params=job.params,
        state=job.state,
        exit_code=job.exit_code,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("/tools")
def list_tools(_: Operator = Depends(get_current_operator)) -> list[dict]:
    return [
        {
            "name": t.name,
            "required_action": t.required_action.value,
            "intrusive": t.required_action in INTRUSIVE_ACTIONS,
            "image": t.image,
        }
        for t in tool_registry.all_tools()
    ]


@router.post("/jobs", response_model=JobOut, status_code=202)
async def submit_job(
    body: JobSubmitRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("operator")),
) -> JobOut:
    try:
        job = job_service.submit(
            db,
            tool=body.tool,
            target=body.target,
            params=body.params,
            operator_id=operator.id,
            confirm_intrusive=body.confirm_intrusive,
        )
    except UnknownTool as exc:
        raise HTTPException(status_code=404, detail=f"unknown tool: {exc}") from exc
    except IntrusiveConfirmationRequired as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "requires_confirmation": True, "action": exc.action},
        ) from exc
    except NoActiveEngagement as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail=f"out of scope: {exc.decision.reason}") from exc
    except Exception as exc:
        # ToolParamError and friends -> 422
        from azami.tools.base import ToolParamError

        if isinstance(exc, ToolParamError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise
    return _to_out(job)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    state: str | None = None,
    db: Session = Depends(get_db),
    _: Operator = Depends(get_current_operator),
) -> list[JobOut]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if state:
        stmt = stmt.where(Job.state == state)
    return [_to_out(j) for j in db.execute(stmt.limit(500)).scalars()]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str, db: Session = Depends(get_db), _: Operator = Depends(get_current_operator)
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_out(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: Operator = Depends(require_role("operator")),
) -> dict:
    ok = job_service.cancel(db, job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="job is not cancellable (not running/queued)")
    return {"cancelled": True}
