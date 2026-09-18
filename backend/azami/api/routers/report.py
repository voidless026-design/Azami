"""Report endpoints: JSON + Markdown engagement report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from azami.auth.deps import require_role
from azami.engagement import manager
from azami.persistence.db import get_db
from azami.persistence.models import Operator
from azami.report import service

router = APIRouter(prefix="/api/report", tags=["report"])


def _eid() -> str:
    eid = manager.active_engagement_id
    if eid is None:
        raise HTTPException(status_code=423, detail="locked: no active engagement")
    return eid


@router.get("")
def report_json(
    db: Session = Depends(get_db), _: Operator = Depends(require_role("reviewer"))
) -> dict:
    return service.build_report(db, _eid())


@router.get("/markdown", response_class=PlainTextResponse)
def report_markdown(
    db: Session = Depends(get_db), _: Operator = Depends(require_role("reviewer"))
) -> str:
    return service.to_markdown(service.build_report(db, _eid()))
