"""Pydantic models for the Rules-of-Engagement (RoE) scope file, plus the Action ladder."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Action(str, Enum):
    """The escalating action ladder. A class must grant the action or it is denied."""

    PASSIVE = "passive"
    ACTIVE_SCAN = "active_scan"
    ACTIVE_TESTING = "active_testing"
    EXPLOITATION = "exploitation"


# Actions that are considered "intrusive" and require a per-run operator confirmation.
INTRUSIVE_ACTIONS = {Action.ACTIVE_TESTING, Action.EXPLOITATION}


class AllowedActions(BaseModel):
    passive: bool = False
    active_scan: bool = False
    active_testing: bool = False
    exploitation: bool = False

    def grants(self, action: Action) -> bool:
        return bool(getattr(self, action.value, False))


class AssetClass(BaseModel):
    name: str
    domains: list[str] = Field(default_factory=list)
    ip_ranges: list[str] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    asns: list[str] = Field(default_factory=list)
    allowed_actions: AllowedActions = Field(default_factory=AllowedActions)


class OutOfScope(BaseModel):
    domains: list[str] = Field(default_factory=list)
    ip_ranges: list[str] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)
    notes: str | None = None


class BlackoutWindow(BaseModel):
    days: list[str] = Field(default_factory=list)  # ["Mon","Tue",...]
    start: str  # "13:00Z"
    end: str  # "21:00Z"


class TimeWindow(BaseModel):
    not_before: datetime
    not_after: datetime
    blackout_windows: list[BlackoutWindow] = Field(default_factory=list)


class Contact(BaseModel):
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None


class EngagementMeta(BaseModel):
    id: str
    client_name: str
    assessing_org: str
    authorization_ref: str
    authorizing_contact: Contact = Field(default_factory=Contact)
    emergency_stop_contact: Contact = Field(default_factory=Contact)


class Constraints(BaseModel):
    max_scan_rate_pps: int | None = None
    max_global_concurrency: int | None = None
    max_per_host_concurrency: int | None = None
    allowed_source_ips: list[str] = Field(default_factory=list)
    # Tool-specific limits (e.g. hydra: {max_threads: 4}) kept flexible.
    tool_limits: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class Integrity(BaseModel):
    signature_file: str | None = None
    authorizer_pubkey_fingerprint: str | None = None
    # Raw ed25519 public key (base64) for the built-in "azami-ed25519" scheme.
    authorizer_pubkey: str | None = None
    signature_scheme: str = "azami-ed25519"  # azami-ed25519 | minisign | gpg


class Scope(BaseModel):
    schema_version: int = 1
    engagement: EngagementMeta
    time_window: TimeWindow
    in_scope: list[AssetClass] = Field(default_factory=list)
    out_of_scope: OutOfScope = Field(default_factory=OutOfScope)
    constraints: Constraints = Field(default_factory=Constraints)
    integrity: Integrity = Field(default_factory=Integrity)
