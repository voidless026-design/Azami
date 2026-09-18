"""Operator management and authentication."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from azami.config import get_settings
from azami.persistence.models import Operator
from azami.security.passwords import hash_password, verify_password

VALID_ROLES = {"lead", "operator", "reviewer"}


def create_operator(db: Session, username: str, password: str, role: str = "operator") -> Operator:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    operator = Operator(username=username, hashed_password=hash_password(password), role=role)
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator


def get_by_username(db: Session, username: str) -> Operator | None:
    return db.execute(select(Operator).where(Operator.username == username)).scalar_one_or_none()


def authenticate(db: Session, username: str, password: str) -> Operator | None:
    operator = get_by_username(db, username)
    if operator is None or not operator.active:
        return None
    if not verify_password(password, operator.hashed_password):
        return None
    return operator


def ensure_bootstrap_admin(db: Session) -> None:
    """Create the default lead operator on first boot if no operators exist."""
    settings = get_settings()
    existing = db.execute(select(Operator).limit(1)).scalar_one_or_none()
    if existing is not None:
        return
    create_operator(
        db,
        settings.bootstrap_admin_username,
        settings.bootstrap_admin_password,
        role="lead",
    )
