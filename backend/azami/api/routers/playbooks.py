"""Playbook endpoints: list builtins, run one against a root target."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from azami.auth.deps import get_current_operator, require_role
from azami.engagement import NoActiveEngagement
from azami.orchestration.engine import run_playbook
from azami.orchestration.playbook import BUILTIN
from azami.persistence.db import get_db
from azami.persistence.models import Operator

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


class PlaybookRunRequest(BaseModel):
    target: str


@router.get("")
def list_playbooks(_: Operator = Depends(get_current_operator)) -> list[dict]:
    return [
        {
            "name": pb.name,
            "description": pb.description,
            "steps": [
                {"id": s.id, "action": s.action, "name": s.name, "targets": s.targets}
                for s in pb.steps
            ],
        }
        for pb in BUILTIN.values()
    ]


@router.post("/{name}/run")
async def run(
    name: str,
    body: PlaybookRunRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_role("operator")),
) -> dict:
    pb = BUILTIN.get(name)
    if pb is None:
        raise HTTPException(status_code=404, detail="unknown playbook")
    try:
        return await run_playbook(
            db, playbook=pb, root_target=body.target, operator_id=operator.id
        )
    except NoActiveEngagement as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
