"""Passive OSINT endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from azami.api.schemas import CollectRequest
from azami.auth.deps import get_current_operator, require_role
from azami.engagement import NoActiveEngagement, ScopeDenied
from azami.osint import registry
from azami.osint.runner import run_collectors
from azami.persistence.db import get_db
from azami.persistence.models import Operator

router = APIRouter(prefix="/api/osint", tags=["osint"])


@router.get("/collectors")
def list_collectors(_: Operator = Depends(get_current_operator)) -> list[dict]:
    return [
        {
            "name": c.name,
            "applies_to": sorted(c.applies_to),
            "requires_action": c.requires_action.value,
            "enabled": c.enabled,
            "produces": [p.value for p in c.produces],
        }
        for c in registry.all_collectors()
    ]


@router.post("/collect")
async def collect(
    body: CollectRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("operator")),
) -> dict:
    try:
        return await run_collectors(
            db, target=body.target, operator_id=operator.id, sources=body.sources
        )
    except NoActiveEngagement as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail=f"out of scope: {exc.decision.reason}") from exc
