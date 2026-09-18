"""Passive OSINT runner: scope-gate the target, run applicable collectors, persist entities."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from azami.engagement import manager
from azami.entities import service as entity_service
from azami.entities.canonical import EntityType
from azami.osint import registry
from azami.scope.canonical import TargetKind, canonicalize
from azami.scope.schema import Action

log = logging.getLogger("azami.osint")


def classify(target: str) -> tuple[str, str, str]:
    """Return (kind, collection_value, gate_target).

    - email  -> kind 'email', value = the email, gate on its domain
    - ip     -> kind 'ip',    value/gate = the ip
    - domain -> kind 'domain',value/gate = the host
    """
    t = target.strip()
    if "@" in t and "://" not in t:
        domain = t.split("@", 1)[1].strip().lower()
        return "email", t.lower(), domain
    ct = canonicalize(t)
    if ct.kind is TargetKind.IP:
        return "ip", ct.value, ct.value
    return "domain", ct.value, ct.value


async def run_collectors(
    db: Session,
    *,
    target: str,
    operator_id: str | None,
    sources: list[str] | None = None,
) -> dict:
    """Gate the target (passive), run collectors concurrently, persist results.

    Raises NoActiveEngagement / ScopeDenied (handled by the API layer).
    """
    kind, value, gate_target = classify(target)

    # One scope decision (audited) for the whole passive collection request.
    manager.gate(
        db,
        target=gate_target,
        action=Action.PASSIVE,
        label="osint.collect",
        operator_id=operator_id,
        params={"target": target, "sources": sources},
    )
    engagement_id = manager.active_engagement_id

    collectors = registry.applicable(kind, sources)
    results = await asyncio.gather(
        *[c.collect(value, kind) for c in collectors], return_exceptions=True
    )

    summary: list[dict] = []
    entity_ids: set[str] = set()

    # Seed the root target as an entity so the graph has an anchor node.
    root_type = {"ip": EntityType.IP, "email": EntityType.EMAIL}.get(kind, EntityType.DOMAIN)
    root = entity_service.upsert_entity(
        db,
        engagement_id=engagement_id,
        entity_type=root_type,
        dedup_key=value,
        fields={"seed": True, kind: value},
        source="seed",
        confidence=0.5,
    )
    entity_ids.add(root.id)

    for collector, result in zip(collectors, results, strict=False):
        if isinstance(result, Exception):
            log.warning("collector %s failed: %s", collector.name, result)
            summary.append({"collector": collector.name, "count": 0, "error": str(result)})
            continue
        for rec in result:
            ent = entity_service.upsert_entity(
                db,
                engagement_id=engagement_id,
                entity_type=rec.entity_type,
                dedup_key=rec.dedup_key,
                fields=rec.fields,
                source=collector.name,
                field_values=rec.field_values,
            )
            entity_ids.add(ent.id)
        summary.append({"collector": collector.name, "count": len(result), "error": None})

    return {
        "target": target,
        "kind": kind,
        "collectors": summary,
        "entities": len(entity_ids),
    }
