"""Quickstart: build + load a scope from a form (no YAML) and confirm the gate still works."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from azami.persistence.db import Base, engine, init_db

    Base.metadata.drop_all(engine)
    init_db()
    from azami.main import app

    with TestClient(app) as c:
        yield c


def _auth(client) -> dict:
    r = client.post("/api/auth/token", data={"username": "admin", "password": "changeme"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_quickstart_no_yaml(client):
    h = _auth(client)
    assert client.get("/api/engagement/status").json()["locked"] is True

    r = client.post(
        "/api/engagement/quickstart",
        json={
            "targets": ["example.com", "203.0.113.0/24", "10.0.0.5"],
            "allow_active_scan": True,
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert client.get("/api/engagement/status").json()["locked"] is False

    def check(target, action="active_scan"):
        return client.post(
            "/api/engagement/check", json={"target": target, "action": action}, headers=h
        ).json()

    assert check("example.com", "passive")["allowed"]
    assert check("api.example.com")["allowed"]  # wildcard subdomain
    assert check("203.0.113.10")["allowed"]  # inside the CIDR
    assert check("10.0.0.5")["allowed"]  # exact host IP
    assert check("evil.org")["allowed"] is False  # not in scope
    # active_testing not granted by the quickstart defaults
    assert check("example.com", "active_testing")["allowed"] is False


def test_quickstart_requires_targets(client):
    h = _auth(client)
    r = client.post("/api/engagement/quickstart", json={"targets": ["  "]}, headers=h)
    assert r.status_code == 422
