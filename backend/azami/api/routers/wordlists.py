"""Wordlist management endpoints."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from azami.auth.deps import get_current_operator, require_role
from azami.persistence.models import Operator
from azami.wordlists import manager

router = APIRouter(prefix="/api/wordlists", tags=["wordlists"])


@router.get("")
def list_wordlists(_: Operator = Depends(get_current_operator)) -> list[dict]:
    return manager.status()


@router.post("/{name}/install")
def install_wordlist(
    name: str, _: Operator = Depends(require_role("operator"))
) -> dict:
    try:
        return manager.install(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"download failed: {exc}") from exc
