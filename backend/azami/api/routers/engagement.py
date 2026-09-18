"""Engagement/scope endpoints: status, load scope, kill-switch, dry-run gate check."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.api.schemas import (
    CheckRequest,
    DecisionOut,
    EngagementOut,
    KillSwitchOut,
    QuickScopeRequest,
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


def _build_quick_scope(body: QuickScopeRequest) -> dict:
    """Turn a simple target list + toggles into a full scope object (no YAML authoring)."""
    domains: list[str] = []
    ip_ranges: list[str] = []
    hosts: list[str] = []
    for raw in body.targets:
        t = raw.strip()
        if not t:
            continue
        if "/" in t:
            try:
                ipaddress.ip_network(t, strict=False)
                ip_ranges.append(t)
                continue
            except ValueError:
                pass
        try:
            ipaddress.ip_address(t)
            hosts.append(t)  # exact-IP match
            continue
        except ValueError:
            pass
        # Treat as a domain; also authorize its subdomains for convenience.
        domains.append(t)
        if not t.startswith("*."):
            domains.append(f"*.{t}")

    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "engagement": {
            "id": body.engagement_id or f"QUICK-{now:%Y%m%d-%H%M%S}",
            "client_name": body.client_name,
            "assessing_org": "Azami operator",
            "authorization_ref": "quickstart (operator-declared authorization)",
        },
        "time_window": {
            "not_before": now.isoformat(),
            "not_after": (now + timedelta(days=max(1, body.days_valid))).isoformat(),
        },
        "in_scope": [
            {
                "name": "targets",
                "domains": domains,
                "ip_ranges": ip_ranges,
                "hosts": hosts,
                "allowed_actions": {
                    "passive": True,
                    "active_scan": body.allow_active_scan,
                    "active_testing": body.allow_active_testing,
                    "exploitation": body.allow_exploitation,
                },
            }
        ],
    }


@router.post("/quickstart", response_model=EngagementOut)
def quickstart(
    body: QuickScopeRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("lead")),
) -> EngagementOut:
    """Authorize an engagement from a simple form (targets + toggles) — no YAML needed."""
    if not any(t.strip() for t in body.targets):
        raise HTTPException(status_code=422, detail="at least one target is required")
    scope_text = yaml.safe_dump(_build_quick_scope(body), sort_keys=False)
    try:
        eng = manager.load(db, scope_text=scope_text, operator_id=operator.id)
    except SignatureError as exc:
        # Only reachable if unsigned scopes are disallowed (production).
        raise HTTPException(
            status_code=400,
            detail=(
                "quickstart builds an unsigned scope, which this deployment disallows "
                "(AZAMI_ALLOW_UNSIGNED_SCOPES=false); load a signed scope instead. "
                f"({exc})"
            ),
        ) from exc
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
