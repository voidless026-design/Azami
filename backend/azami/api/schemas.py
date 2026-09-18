"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from azami.scope.schema import Action


# --- auth -------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class OperatorOut(BaseModel):
    id: str
    username: str
    role: str
    active: bool


class OperatorCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"


# --- engagement / scope -----------------------------------------------------
class ScopeLoadRequest(BaseModel):
    scope_text: str
    signature_b64: str | None = None


class QuickScopeRequest(BaseModel):
    """Build + load a scope from a simple form — no YAML authoring required."""

    targets: list[str]
    engagement_id: str | None = None
    client_name: str = "Self-authorized assessment"
    allow_active_scan: bool = True
    allow_active_testing: bool = False
    allow_exploitation: bool = False
    days_valid: int = 30


class EngagementOut(BaseModel):
    id: str
    engagement_ref: str
    client_name: str
    assessing_org: str
    authorization_ref: str
    signature_verified: bool
    not_before: datetime
    not_after: datetime
    status: str


class StatusOut(BaseModel):
    locked: bool
    now: datetime
    engagement: EngagementOut | None = None
    signature_verified: bool = False


class CheckRequest(BaseModel):
    target: str
    action: Action = Action.PASSIVE


class DecisionOut(BaseModel):
    allowed: bool
    reason: str
    asset_class: str | None = None
    intrusive: bool = False


class KillSwitchOut(BaseModel):
    cancelled_jobs: int


# --- audit ------------------------------------------------------------------
class AuditRecordOut(BaseModel):
    seq: int
    id: str
    ts: datetime
    engagement_id: str | None
    operator_id: str | None
    action: str
    target: str | None
    tool: str | None
    parameters: dict
    scope_decision: str
    result_hash: str | None
    prev_hash: str
    record_hash: str


class ChainStatusOut(BaseModel):
    ok: bool
    length: int
    first_bad_seq: int | None
    detail: str


# --- jobs / tools -----------------------------------------------------------
class JobSubmitRequest(BaseModel):
    tool: str
    target: str
    params: dict = {}
    confirm_intrusive: bool = False


class JobOut(BaseModel):
    id: str
    engagement_id: str
    tool: str
    target: str
    params: dict
    state: str
    exit_code: int | None
    result: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# --- osint ------------------------------------------------------------------
class CollectRequest(BaseModel):
    target: str
    sources: list[str] | None = None  # None => all applicable passive collectors


class EntityOut(BaseModel):
    id: str
    type: str
    dedup_key: str
    fields: dict
    confidence: float
    first_seen: datetime
    last_seen: datetime
