"""Signature verification: valid signature loads, tampered/unsigned are rejected."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from azami.scope.engine import ScopeLoadError, load_scope
from azami.scope.signature import SignatureError

BASE_SCOPE = """
schema_version: 1
engagement:
  id: ENG-SIG
  client_name: Example Corp
  assessing_org: Test Firm
  authorization_ref: SOW-1
time_window:
  not_before: "2026-09-15T00:00:00Z"
  not_after: "2026-09-30T23:59:59Z"
in_scope:
  - name: web
    domains: ["example.com"]
    allowed_actions: {passive: true}
integrity:
  signature_scheme: azami-ed25519
  authorizer_pubkey: "%PUBKEY%"
"""


def _keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    from cryptography.hazmat.primitives import serialization

    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return priv, base64.b64encode(pub_raw).decode()


def test_valid_signature_loads():
    priv, pub_b64 = _keypair()
    text = BASE_SCOPE.replace("%PUBKEY%", pub_b64)
    sig = base64.b64encode(priv.sign(text.encode())).decode()
    scope, verified = load_scope(text, allow_unsigned=False, signature_b64=sig)
    assert verified and scope.engagement.id == "ENG-SIG"


def test_tampered_scope_rejected():
    priv, pub_b64 = _keypair()
    text = BASE_SCOPE.replace("%PUBKEY%", pub_b64)
    sig = base64.b64encode(priv.sign(text.encode())).decode()
    tampered = text.replace("example.com", "evil.com")
    with pytest.raises(SignatureError):
        load_scope(tampered, allow_unsigned=False, signature_b64=sig)


def test_unsigned_rejected_when_not_allowed():
    _, pub_b64 = _keypair()
    text = BASE_SCOPE.replace("%PUBKEY%", pub_b64)
    with pytest.raises(SignatureError):
        load_scope(text, allow_unsigned=False, signature_b64=None)


def test_unsigned_allowed_in_dev_mode():
    _, pub_b64 = _keypair()
    text = BASE_SCOPE.replace("%PUBKEY%", pub_b64)
    scope, verified = load_scope(text, allow_unsigned=True, signature_b64=None)
    assert not verified and scope.engagement.id == "ENG-SIG"


def test_bad_yaml_rejected():
    with pytest.raises(ScopeLoadError):
        load_scope("::: not yaml :::\n  - [", allow_unsigned=True)
