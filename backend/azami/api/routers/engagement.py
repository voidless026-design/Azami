"""Engagement/scope endpoints: status, load scope, kill-switch, dry-run gate check."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.api.schemas import (
    CheckRequest,
    DecisionOut,
    EngagementOut,
    KillSwitchOut,
    ScopeLoadRequest,
    StatusOut,
)
from azami.auth.deps import get_current_operator, require_role
from azami.engagement import NoActiveEngagement, ScopeDenied, manager
from azami.persistence.db import get_db
from azami.persistence.models import Engagement, Operator
from azami.scope.engine import ScopeLoadError
from azami.scope.signature import SignatureError

router = APIRouter(prefix="/api/engagement", tags=["engagement"])


def _to_out(e: Engagement) -> EngagementOut:
    return EngagementOut(
        id=e.id,
        engagement_ref=e.engagement_ref,
        client_name=e.client_name,
        assessing_org=e.assessing_org,
        authorization_ref=e.authorization_ref,
        signature_verified=e.signature_verified,
        not_before=e.not_before,
        not_after=e.not_after,
        status=e.status,
    )


@router.get("/status", response_model=StatusOut, tags=["status"])
def status(db: Session = Depends(get_db)) -> StatusOut:
    now = datetime.now(timezone.utc)
    if manager.is_locked():
        return StatusOut(locked=True, now=now)
    eng = db.get(Engagement, manager.active_engagement_id)
    return StatusOut(
        locked=False,
        now=now,
        engagement=_to_out(eng) if eng else None,
        signature_verified=eng.signature_verified if eng else False,
    )


@router.post("/load", response_model=EngagementOut)
def load_scope(
    body: ScopeLoadRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("lead")),
) -> EngagementOut:
    try:
        eng = manager.load(
            db,
            scope_text=body.scope_text,
            operator_id=operator.id,
            signature_b64=body.signature_b64,
        )
    except SignatureError as exc:
        raise HTTPException(status_code=400, detail=f"signature error: {exc}") from exc
    except ScopeLoadError as exc:
        raise HTTPException(status_code=422, detail=f"scope error: {exc}") from exc
    return _to_out(eng)


@router.post("/kill-switch", response_model=KillSwitchOut)
def kill_switch(
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("lead")),
) -> KillSwitchOut:
    cancelled = manager.kill_switch(db, operator_id=operator.id)
    return KillSwitchOut(cancelled_jobs=cancelled)


@router.get("/scope")
def current_scope(_: Operator = Depends(get_current_operator)):
    engine = manager.get_engine()
    if engine is None:
        raise HTTPException(status_code=423, detail="locked: no active engagement")
    return engine.scope.model_dump(mode="json")


@router.post("/check", response_model=DecisionOut)
def check(
    body: CheckRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(get_current_operator),
) -> DecisionOut:
    """Dry-run the gate for a target/action. Audited as a scope.check."""
    try:
        decision = manager.gate(
            db,
            target=body.target,
            action=body.action,
            label="scope.check",
            operator_id=operator.id,
        )
    except NoActiveEngagement as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except ScopeDenied as exc:
        d = exc.decision
        return DecisionOut(
            allowed=False, reason=d.reason, asset_class=d.asset_class, intrusive=d.intrusive
        )
    return DecisionOut(
        allowed=decision.allowed,
        reason=decision.reason,
        asset_class=decision.asset_class,
        intrusive=decision.intrusive,
    )


@router.get("/history", response_model=list[EngagementOut])
def history(
    db: Session = Depends(get_db), _: Operator = Depends(get_current_operator)
) -> list[EngagementOut]:
    rows = db.execute(select(Engagement).order_by(Engagement.created_at.desc())).scalars().all()
    return [_to_out(e) for e in rows]
