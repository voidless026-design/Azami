"""End-to-end Phase 0: lock -> login -> load scope -> gate -> audit -> kill-switch."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

SCOPE_YAML = """
schema_version: 1
engagement:
  id: ENG-API
  client_name: Example Corp
  assessing_org: Test Firm
  authorization_ref: SOW-API
time_window:
  not_before: "2020-01-01T00:00:00Z"
  not_after: "2035-12-31T23:59:59Z"
in_scope:
  - name: web
    domains: ["example.com", "*.example.com"]
    allowed_actions: {passive: true, active_scan: true}
out_of_scope:
  hosts: ["payments.example.com"]
"""


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
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_flow(client):
    h = _auth(client)

    # Starts locked.
    assert client.get("/api/engagement/status").json()["locked"] is True

    # A gate check while locked is refused (423).
    r = client.post("/api/engagement/check", json={"target": "example.com"}, headers=h)
    assert r.status_code == 423

    # Load a scope -> unlocks.
    r = client.post("/api/engagement/load", json={"scope_text": SCOPE_YAML}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["engagement_ref"] == "ENG-API"
    assert r.json()["signature_verified"] is False  # unsigned dev scope

    assert client.get("/api/engagement/status").json()["locked"] is False

    # In-scope allowed, out-of-scope denied.
    allow = client.post(
        "/api/engagement/check",
        json={"target": "api.example.com", "action": "active_scan"},
        headers=h,
    ).json()
    assert allow["allowed"] and allow["asset_class"] == "web"

    deny = client.post(
        "/api/engagement/check", json={"target": "payments.example.com"}, headers=h
    ).json()
    assert deny["allowed"] is False and "excluded" in deny["reason"]

    notinscope = client.post(
        "/api/engagement/check", json={"target": "evil.org"}, headers=h
    ).json()
    assert notinscope["allowed"] is False

    # Audit chain intact and populated.
    v = client.get("/api/audit/verify", headers=h).json()
    assert v["ok"] and v["length"] >= 4

    # Kill switch re-locks.
    ks = client.post("/api/engagement/kill-switch", headers=h)
    assert ks.status_code == 200
    assert client.get("/api/engagement/status").json()["locked"] is True


def test_rbac_reviewer_cannot_load(client):
    admin = _auth(client)
    # Create a reviewer.
    client.post(
        "/api/auth/operators",
        json={"username": "rev", "password": "pw", "role": "reviewer"},
        headers=admin,
    )
    r = client.post("/api/auth/token", data={"username": "rev", "password": "pw"})
    rev = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Reviewer cannot load a scope (needs lead).
    assert client.post(
        "/api/engagement/load", json={"scope_text": SCOPE_YAML}, headers=rev
    ).status_code == 403
