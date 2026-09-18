"""Test config: isolate the DB/data dir to a temp location before importing app modules."""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="azami-test-")
os.environ.setdefault("AZAMI_DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("AZAMI_DATA_DIR", _TMP)
os.environ.setdefault("AZAMI_WORDLISTS_DIR", f"{_TMP}/wordlists")
os.environ.setdefault("AZAMI_ALLOW_UNSIGNED_SCOPES", "true")
os.environ.setdefault("AZAMI_JWT_SECRET", "test-secret")

import pytest  # noqa: E402


@pytest.fixture
def db():
    from azami.persistence.db import Base, SessionLocal, engine, init_db

    Base.metadata.drop_all(engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
