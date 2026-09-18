"""Entity resolution & persistence: deterministic dedup + confidence aggregation."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.entities.canonical import EntityType
from azami.entities.confidence import corroborate, source_weight
from azami.persistence.models import Assertion, Entity


def upsert_entity(
    db: Session,
    *,
    engagement_id: str,
    entity_type: EntityType,
    dedup_key: str,
    fields: dict,
    source: str,
    field_values: dict | None = None,
    confidence: float | None = None,
) -> Entity:
    """Insert or merge an entity by (engagement, type, dedup_key).

    - New entity: confidence = source weight (or override).
    - Existing entity: fields merged, confidence corroborated upward, last_seen bumped.
    Every field/value becomes an Assertion carrying its source + confidence (provenance).
    """
    weight = confidence if confidence is not None else source_weight(source)
    dedup_key = dedup_key.strip().lower()

    entity = db.execute(
        select(Entity).where(
            Entity.engagement_id == engagement_id,
            Entity.type == entity_type.value,
            Entity.dedup_key == dedup_key,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if entity is None:
        entity = Entity(
            engagement_id=engagement_id,
            type=entity_type.value,
            dedup_key=dedup_key,
            fields=dict(fields),
            confidence=round(weight, 4),
            first_seen=now,
            last_seen=now,
        )
        db.add(entity)
    else:
        merged = dict(entity.fields or {})
        merged.update(fields)
        entity.fields = merged
        entity.confidence = corroborate(entity.confidence, weight)
        entity.last_seen = now

    db.flush()  # ensure entity.id

    for field, value in (field_values or fields).items():
        if value is None:
            continue
        db.add(
            Assertion(
                entity_id=entity.id,
                source=source,
                field=str(field),
                value=str(value),
                confidence=round(weight, 4),
                ts=now,
            )
        )

    db.commit()
    db.refresh(entity)
    return entity


def list_entities(db: Session, engagement_id: str, entity_type: str | None = None) -> list[Entity]:
    stmt = select(Entity).where(Entity.engagement_id == engagement_id)
    if entity_type:
        stmt = stmt.where(Entity.type == entity_type)
    return list(db.execute(stmt.order_by(Entity.confidence.desc())).scalars())


def build_graph(db: Session, engagement_id: str) -> dict:
    """A simple relationship graph: nodes = entities, edges = shared assertion values.

    Edges connect entities that reference each other's dedup_key in their field values
    (e.g. a DOMAIN whose 'a_records' contain an IP that is also an IP entity).
    """
    entities = list_entities(db, engagement_id)
    nodes = [
        {
            "id": e.id,
            "type": e.type,
            "label": e.dedup_key,
            "confidence": e.confidence,
            "fields": e.fields,
        }
        for e in entities
    ]
    key_to_id = {e.dedup_key: e.id for e in entities}
    edges = []
    for e in entities:
        for value in _iter_values(e.fields):
            v = str(value).strip().lower()
            if v in key_to_id and key_to_id[v] != e.id:
                edges.append({"source": e.id, "target": key_to_id[v]})
    return {"nodes": nodes, "edges": edges}


def _iter_values(fields: dict):
    for v in (fields or {}).values():
        if isinstance(v, (list, tuple)):
            yield from v
        else:
            yield v
