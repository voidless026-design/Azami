"""Audit endpoints: list, verify chain, export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.api.schemas import AuditRecordOut, ChainStatusOut
from azami.audit.log import AuditLogger
from azami.auth.deps import require_role
from azami.persistence.db import get_db
from azami.persistence.models import AuditRecord, Operator

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _to_out(r: AuditRecord) -> AuditRecordOut:
    return AuditRecordOut(
        seq=r.seq,
        id=r.id,
        ts=r.ts,
        engagement_id=r.engagement_id,
        operator_id=r.operator_id,
        action=r.action,
        target=r.target,
        tool=r.tool,
        parameters=r.parameters,
        scope_decision=r.scope_decision,
        result_hash=r.result_hash,
        prev_hash=r.prev_hash,
        record_hash=r.record_hash,
    )


@router.get("", response_model=list[AuditRecordOut])
def list_audit(
    db: Session = Depends(get_db),
    _: Operator = Depends(require_role("reviewer")),
    limit: int = Query(200, le=1000),
    offset: int = 0,
    engagement_id: str | None = None,
) -> list[AuditRecordOut]:
    stmt = select(AuditRecord).order_by(AuditRecord.seq.desc())
    if engagement_id:
        stmt = stmt.where(AuditRecord.engagement_id == engagement_id)
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()
    return [_to_out(r) for r in rows]


@router.get("/verify", response_model=ChainStatusOut)
def verify(
    db: Session = Depends(get_db), _: Operator = Depends(require_role("reviewer"))
) -> ChainStatusOut:
    s = AuditLogger(db).verify_chain()
    return ChainStatusOut(ok=s.ok, length=s.length, first_bad_seq=s.first_bad_seq, detail=s.detail)
