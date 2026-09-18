"""FastAPI auth dependencies: current operator + RBAC."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from azami.auth.tokens import TokenError, decode_token
from azami.persistence.db import get_db
from azami.persistence.models import Operator

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Role hierarchy: a higher role satisfies a requirement for a lower one.
_ROLE_RANK = {"reviewer": 0, "operator": 1, "lead": 2}


def get_current_operator(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Operator:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except TokenError as exc:
        raise creds_exc from exc
    operator = db.get(Operator, payload.get("sub"))
    if operator is None or not operator.active:
        raise creds_exc
    return operator


def require_role(minimum: str) -> Callable[[Operator], Operator]:
    """Dependency factory enforcing a minimum role."""
    required_rank = _ROLE_RANK[minimum]

    def _checker(operator: Operator = Depends(get_current_operator)) -> Operator:
        if _ROLE_RANK.get(operator.role, -1) < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role '{minimum}' or higher",
            )
        return operator

    return _checker
