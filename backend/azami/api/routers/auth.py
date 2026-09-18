"""Auth endpoints: token issuance, current operator, operator management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from azami.api.schemas import OperatorCreate, OperatorOut, Token
from azami.auth import service
from azami.auth.deps import get_current_operator, require_role
from azami.auth.tokens import create_access_token
from azami.persistence.db import get_db
from azami.persistence.models import Operator

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    operator = service.authenticate(db, form.username, form.password)
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(operator.id, operator.role)
    return Token(access_token=token, role=operator.role)


@router.get("/me", response_model=OperatorOut)
def me(operator: Operator = Depends(get_current_operator)) -> OperatorOut:
    return OperatorOut(
        id=operator.id, username=operator.username, role=operator.role, active=operator.active
    )


@router.post("/operators", response_model=OperatorOut, status_code=201)
def create_operator(
    body: OperatorCreate,
    db: Session = Depends(get_db),
    _: Operator = Depends(require_role("lead")),
) -> OperatorOut:
    if service.get_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="username already exists")
    try:
        op = service.create_operator(db, body.username, body.password, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OperatorOut(id=op.id, username=op.username, role=op.role, active=op.active)
