"""Entity endpoints: list, detail (with assertions), and relationship graph."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from azami.api.schemas import EntityOut
from azami.auth.deps import get_current_operator
from azami.engagement import manager
from azami.entities import service as entity_service
from azami.persistence.db import get_db
from azami.persistence.models import Entity, Operator

router = APIRouter(prefix="/api/entities", tags=["entities"])


def _require_engagement() -> str:
    eid = manager.active_engagement_id
    if eid is None:
        raise HTTPException(status_code=423, detail="locked: no active engagement")
    return eid


@router.get("", response_model=list[EntityOut])
def list_entities(
    type: str | None = None,
    db: Session = Depends(get_db),
    _: Operator = Depends(get_current_operator),
) -> list[EntityOut]:
    eid = _require_engagement()
    rows = entity_service.list_entities(db, eid, type)
    return [
        EntityOut(
            id=e.id,
            type=e.type,
            dedup_key=e.dedup_key,
            fields=e.fields,
            confidence=e.confidence,
            first_seen=e.first_seen,
            last_seen=e.last_seen,
        )
        for e in rows
    ]


@router.get("/graph")
def graph(db: Session = Depends(get_db), _: Operator = Depends(get_current_operator)) -> dict:
    return entity_service.build_graph(db, _require_engagement())


@router.get("/{entity_id}")
def detail(
    entity_id: str, db: Session = Depends(get_db), _: Operator = Depends(get_current_operator)
) -> dict:
    e = db.get(Entity, entity_id)
    if e is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return {
        "id": e.id,
        "type": e.type,
        "dedup_key": e.dedup_key,
        "fields": e.fields,
        "confidence": e.confidence,
        "first_seen": e.first_seen,
        "last_seen": e.last_seen,
        "assertions": [
            {"source": a.source, "field": a.field, "value": a.value, "confidence": a.confidence}
            for a in e.assertions
        ],
    }
