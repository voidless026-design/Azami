"""Audit log: chain integrity, tamper detection, and secret redaction."""
from __future__ import annotations

from azami.audit.log import AuditLogger
from azami.persistence.models import AuditRecord


def test_chain_intact_after_multiple_records(db):
    log = AuditLogger(db)
    for i in range(5):
        log.record(action=f"act{i}", scope_decision="allow", target=f"t{i}.example.com")
    status = log.verify_chain()
    assert status.ok and status.length == 5


def test_tamper_is_detected(db):
    log = AuditLogger(db)
    log.record(action="a", scope_decision="allow", target="a.example.com")
    rec = log.record(action="b", scope_decision="allow", target="b.example.com")
    log.record(action="c", scope_decision="allow", target="c.example.com")

    # Tamper with the middle record's stored content directly.
    row = db.get(AuditRecord, rec.seq)
    row.target = "evil.example.com"
    db.commit()

    status = log.verify_chain()
    assert not status.ok
    assert status.first_bad_seq == rec.seq


def test_secrets_are_redacted(db):
    log = AuditLogger(db)
    rec = log.record(
        action="run",
        scope_decision="allow",
        tool="hydra",
        parameters={"password": "hunter2", "username": "admin", "nested": {"api_key": "xyz"}},
    )
    stored = db.get(AuditRecord, rec.seq)
    assert stored.parameters["password"] == "***REDACTED***"
    assert stored.parameters["nested"]["api_key"] == "***REDACTED***"
    assert stored.parameters["username"] == "admin"


def test_deletion_breaks_chain(db):
    log = AuditLogger(db)
    log.record(action="a", scope_decision="allow")
    rec = log.record(action="b", scope_decision="allow")
    log.record(action="c", scope_decision="allow")
    db.delete(db.get(AuditRecord, rec.seq))
    db.commit()
    assert not log.verify_chain().ok
