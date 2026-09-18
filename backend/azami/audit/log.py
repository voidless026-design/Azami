"""Append-only, hash-chained audit log.

Every allow/deny decision and every action flows through `AuditLogger.record()`. Records are
chained by `prev_hash` so any edit or deletion breaks the chain and `verify_chain()` reports the
first break. In production the app's DB role should hold INSERT-only rights on this table.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.persistence.models import AuditRecord

GENESIS_HASH = "0" * 64
_REDACT = "***REDACTED***"
_SECRET_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey", "authorization"}


def _redact(params: dict) -> dict:
    out: dict = {}
    for k, v in (params or {}).items():
        if k.lower() in _SECRET_KEYS:
            out[k] = _REDACT
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


def _compute_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ChainStatus:
    ok: bool
    length: int
    first_bad_seq: int | None = None
    detail: str = ""


class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    def _last_hash(self) -> str:
        row = self.db.execute(
            select(AuditRecord).order_by(AuditRecord.seq.desc()).limit(1)
        ).scalar_one_or_none()
        return row.record_hash if row else GENESIS_HASH

    def record(
        self,
        *,
        action: str,
        scope_decision: str,
        engagement_id: str | None = None,
        operator_id: str | None = None,
        target: str | None = None,
        tool: str | None = None,
        parameters: dict | None = None,
        result_hash: str | None = None,
    ) -> AuditRecord:
        prev_hash = self._last_hash()
        ts = datetime.now(timezone.utc)
        params = _redact(parameters or {})
        rec = AuditRecord(
            ts=ts,
            engagement_id=engagement_id,
            operator_id=operator_id,
            action=action,
            target=target,
            tool=tool,
            parameters=params,
            scope_decision=scope_decision,
            result_hash=result_hash,
            prev_hash=prev_hash,
            record_hash="",  # set below
        )
        self.db.add(rec)
        self.db.flush()  # assign id/seq (Python-side defaults) before hashing
        rec.record_hash = _compute_hash(self._payload(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    @staticmethod
    def _canonical_ts(ts) -> str:
        # SQLite drops tzinfo on round-trip, so normalize to naive-UTC for a stable hash.
        if isinstance(ts, datetime):
            if ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
            return ts.isoformat()
        return str(ts)

    @classmethod
    def _payload(cls, rec: AuditRecord) -> dict:
        return {
            "id": rec.id,
            "ts": cls._canonical_ts(rec.ts),
            "engagement_id": rec.engagement_id,
            "operator_id": rec.operator_id,
            "action": rec.action,
            "target": rec.target,
            "tool": rec.tool,
            "parameters": rec.parameters,
            "scope_decision": rec.scope_decision,
            "result_hash": rec.result_hash,
            "prev_hash": rec.prev_hash,
        }

    def verify_chain(self) -> ChainStatus:
        rows = list(
            self.db.execute(select(AuditRecord).order_by(AuditRecord.seq.asc())).scalars()
        )
        prev = GENESIS_HASH
        for rec in rows:
            if rec.prev_hash != prev:
                return ChainStatus(False, len(rows), rec.seq, "prev_hash mismatch")
            if _compute_hash(self._payload(rec)) != rec.record_hash:
                return ChainStatus(False, len(rows), rec.seq, "record_hash mismatch (tampered)")
            prev = rec.record_hash
        return ChainStatus(True, len(rows), None, "chain intact")
