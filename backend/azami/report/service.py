"""Engagement report builder + Markdown export (includes the audit-trail status)."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.audit.log import AuditLogger
from azami.persistence.models import Engagement, Entity, Finding, Job

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]


def build_report(db: Session, engagement_id: str) -> dict:
    eng = db.get(Engagement, engagement_id)
    entities = db.execute(
        select(Entity).where(Entity.engagement_id == engagement_id)
    ).scalars().all()
    findings = db.execute(
        select(Finding).where(Finding.engagement_id == engagement_id)
    ).scalars().all()
    jobs = db.execute(select(Job).where(Job.engagement_id == engagement_id)).scalars().all()
    chain = AuditLogger(db).verify_chain()

    return {
        "engagement": {
            "ref": eng.engagement_ref if eng else None,
            "client": eng.client_name if eng else None,
            "assessing_org": eng.assessing_org if eng else None,
            "authorization_ref": eng.authorization_ref if eng else None,
            "signature_verified": eng.signature_verified if eng else None,
            "window": {
                "not_before": eng.not_before.isoformat() if eng else None,
                "not_after": eng.not_after.isoformat() if eng else None,
            },
        },
        "entities_by_type": dict(Counter(e.type for e in entities)),
        "entities_total": len(entities),
        "findings_by_severity": {
            sev: sum(1 for f in findings if f.severity == sev) for sev in _SEV_ORDER
        },
        "findings": [
            {"title": f.title, "severity": f.severity, "description": f.description}
            for f in sorted(
                findings, key=lambda f: _SEV_ORDER.index(f.severity)
                if f.severity in _SEV_ORDER else 99
            )
        ],
        "jobs_by_tool": dict(Counter(j.tool for j in jobs)),
        "jobs_by_state": dict(Counter(j.state for j in jobs)),
        "audit": {"ok": chain.ok, "length": chain.length, "detail": chain.detail},
    }


def to_markdown(report: dict) -> str:
    e = report["engagement"]
    lines = [
        f"# Engagement Report — {e['ref']}",
        "",
        f"- **Client:** {e['client']}",
        f"- **Assessing org:** {e['assessing_org']}",
        f"- **Authorization:** {e['authorization_ref']} "
        f"(signature verified: {e['signature_verified']})",
        f"- **Window:** {e['window']['not_before']} → {e['window']['not_after']}",
        "",
        "## Attack surface",
        f"- **Entities discovered:** {report['entities_total']}",
    ]
    for etype, count in sorted(report["entities_by_type"].items()):
        lines.append(f"  - {etype}: {count}")
    lines += ["", "## Findings"]
    sev = report["findings_by_severity"]
    lines.append("| Severity | Count |")
    lines.append("|---|---|")
    for s in _SEV_ORDER:
        lines.append(f"| {s} | {sev.get(s, 0)} |")
    lines.append("")
    for f in report["findings"]:
        lines.append(f"### [{f['severity'].upper()}] {f['title']}")
        if f["description"]:
            lines.append(f["description"])
        lines.append("")
    lines += [
        "## Methodology / activity",
        f"- Jobs by tool: {report['jobs_by_tool']}",
        f"- Jobs by state: {report['jobs_by_state']}",
        "",
        "## Audit trail integrity",
        f"- Chain status: {'INTACT' if report['audit']['ok'] else 'BROKEN'} "
        f"({report['audit']['length']} records) — {report['audit']['detail']}",
        "",
        "_The full tamper-evident audit log is available via /api/audit/export._",
    ]
    return "\n".join(lines)
