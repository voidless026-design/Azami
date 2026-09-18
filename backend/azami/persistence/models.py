"""SQLAlchemy models: operators, engagements, audit, entities, jobs, findings, wordlists."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from azami.persistence.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")  # lead|operator|reviewer
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Engagement(Base):
    """A loaded, authorized engagement. Holds the parsed scope and lock state."""

    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    engagement_ref: Mapped[str] = mapped_column(String(128), index=True)  # from scope.engagement.id
    client_name: Mapped[str] = mapped_column(String(255))
    assessing_org: Mapped[str] = mapped_column(String(255))
    authorization_ref: Mapped[str] = mapped_column(String(255))
    scope_raw: Mapped[str] = mapped_column(Text)  # original scope file bytes (text)
    scope_json: Mapped[dict] = mapped_column(JSON)  # parsed scope
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|revoked|expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditRecord(Base):
    """Append-only, hash-chained audit log. App DB role should have INSERT-only here."""

    __tablename__ = "audit_records"

    # seq is the autoincrement PK so the chain has a strict, gap-free-ish order (SQLite
    # only autoincrements the primary key); id remains a stable external uuid.
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_uuid)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    engagement_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)  # secrets redacted
    scope_decision: Mapped[str] = mapped_column(String(512))  # e.g. "allow" / "deny: not in scope"
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), index=True)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)  # EntityType value
    dedup_key: Mapped[str] = mapped_column(String(512), index=True)  # canonical identity key
    fields: Mapped[dict] = mapped_column(JSON, default=dict)  # canonical fields
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assertions: Mapped[list["Assertion"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class Assertion(Base):
    """A single source's claim about an entity field, with provenance and confidence."""

    __tablename__ = "assertions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    source: Mapped[str] = mapped_column(String(64))  # collector/tool name
    field: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    entity: Mapped[Entity] = relationship(back_populates="assertions")


class Job(Base):
    """A tool run with an explicit state machine."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String(36), index=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(512))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # parsed structured result
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info|low|med|high|crit
    description: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Wordlist(Base):
    __tablename__ = "wordlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(512))
    license: Mapped[str] = mapped_column(String(128), default="unknown")
    version: Mapped[str] = mapped_column(String(64), default="")
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
