"""Engagement manager: the runtime home of the active scope + the gate + the kill-switch.

This is the single choke point the rest of the app calls to touch a target. `gate()` runs the
scope decision AND writes the audit record every time, allow or deny. With no active engagement
the app is LOCKED and every gated call raises NoActiveEngagement (HTTP 423).
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.audit.log import AuditLogger
from azami.config import get_settings
from azami.persistence.models import Engagement
from azami.scope.engine import Decision, ScopeEngine, load_scope
from azami.scope.schema import Action


class NoActiveEngagement(Exception):
    """Raised when a gated action is attempted while the app is locked (no scope loaded)."""


class ScopeDenied(Exception):
    def __init__(self, decision: Decision):
        self.decision = decision
        super().__init__(decision.reason)


class EngagementManager:
    """Process-wide singleton holding the in-memory active ScopeEngine."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engine: ScopeEngine | None = None
        self._engagement_id: str | None = None

    # -- state ---------------------------------------------------------------
    @property
    def active_engagement_id(self) -> str | None:
        return self._engagement_id

    def is_locked(self) -> bool:
        return self._engine is None

    def get_engine(self) -> ScopeEngine | None:
        return self._engine

    # -- lifecycle -----------------------------------------------------------
    def load(
        self,
        db: Session,
        *,
        scope_text: str,
        operator_id: str | None,
        signature_b64: str | None = None,
    ) -> Engagement:
        settings = get_settings()
        scope, verified = load_scope(
            scope_text, allow_unsigned=settings.allow_unsigned_scopes, signature_b64=signature_b64
        )
        tw = scope.time_window
        engagement = Engagement(
            engagement_ref=scope.engagement.id,
            client_name=scope.engagement.client_name,
            assessing_org=scope.engagement.assessing_org,
            authorization_ref=scope.engagement.authorization_ref,
            scope_raw=scope_text,
            scope_json=scope.model_dump(mode="json"),
            signature_verified=verified,
            not_before=tw.not_before,
            not_after=tw.not_after,
            status="active",
        )
        db.add(engagement)
        db.commit()
        db.refresh(engagement)

        with self._lock:
            self._engine = ScopeEngine(scope, signature_verified=verified)
            self._engagement_id = engagement.id

        AuditLogger(db).record(
            action="SCOPE_LOADED",
            engagement_id=engagement.id,
            operator_id=operator_id,
            scope_decision=f"loaded (signature_verified={verified})",
            parameters={
                "engagement_ref": scope.engagement.id,
                "authorization_ref": scope.engagement.authorization_ref,
                "signature_verified": verified,
            },
        )
        return engagement

    def kill_switch(self, db: Session, *, operator_id: str | None) -> int:
        """Cancel all running jobs, revoke the active scope, and re-lock the app."""
        engagement_id = self._engagement_id
        cancelled = 0
        if engagement_id:
            try:
                # Lazy import to avoid a cycle with the job service (Phase 2+).
                from azami.jobs.service import job_service

                cancelled = job_service.cancel_all(db, engagement_id)
            except ImportError:
                cancelled = 0
            eng = db.get(Engagement, engagement_id)
            if eng:
                eng.status = "revoked"
                db.commit()

        with self._lock:
            self._engine = None
            self._engagement_id = None

        AuditLogger(db).record(
            action="KILL_SWITCH",
            engagement_id=engagement_id,
            operator_id=operator_id,
            scope_decision="scope revoked; app re-locked",
            parameters={"cancelled_jobs": cancelled},
        )
        return cancelled

    def restore_active(self, db: Session) -> None:
        """On startup, reload the most recent active, in-window engagement into memory."""
        now = datetime.now(timezone.utc)
        row = db.execute(
            select(Engagement)
            .where(Engagement.status == "active")
            .order_by(Engagement.created_at.desc())
        ).scalars().first()
        if row is None:
            return
        if not (row.not_before <= now <= row.not_after):
            row.status = "expired"
            db.commit()
            return
        try:
            scope, verified = load_scope(
                row.scope_raw,
                allow_unsigned=True,  # already validated at load time; DB is trusted here
                signature_b64=None,
            )
        except Exception:  # corrupt row; stay locked
            return
        with self._lock:
            self._engine = ScopeEngine(scope, signature_verified=row.signature_verified)
            self._engagement_id = row.id

    # -- the gate ------------------------------------------------------------
    def gate(
        self,
        db: Session,
        *,
        target: str,
        action: Action,
        label: str,
        operator_id: str | None = None,
        tool: str | None = None,
        params: dict | None = None,
    ) -> Decision:
        """Decide + audit. Raises NoActiveEngagement (locked) or ScopeDenied (out of scope)."""
        engine = self._engine
        if engine is None:
            AuditLogger(db).record(
                action=label,
                target=target,
                tool=tool,
                parameters=params or {},
                scope_decision="deny: no active engagement (locked)",
                operator_id=operator_id,
            )
            raise NoActiveEngagement("no active engagement; load a scope first")

        decision = engine.check(target, action)
        AuditLogger(db).record(
            action=label,
            engagement_id=self._engagement_id,
            operator_id=operator_id,
            target=target,
            tool=tool,
            parameters=params or {},
            scope_decision=str(decision),
        )
        if not decision.allowed:
            raise ScopeDenied(decision)
        return decision


# Process-wide singleton.
manager = EngagementManager()
