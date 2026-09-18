"""Detached-signature verification for scope files.

The built-in scheme "azami-ed25519" verifies a base64 ed25519 signature over the exact
scope-file bytes against a base64 ed25519 public key declared in the scope's integrity block.
minisign and GPG are documented production options; wire them in behind the same interface.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class SignatureError(Exception):
    pass


def verify_ed25519(payload: bytes, signature_b64: str, pubkey_b64: str) -> None:
    """Raise SignatureError unless the signature verifies."""
    try:
        signature = base64.b64decode(signature_b64)
        pubkey_bytes = base64.b64decode(pubkey_b64)
    except (ValueError, TypeError) as exc:
        raise SignatureError(f"malformed base64 in signature/pubkey: {exc}") from exc

    try:
        Ed25519PublicKey.from_public_bytes(pubkey_bytes).verify(signature, payload)
    except InvalidSignature as exc:
        raise SignatureError("signature does not verify against the authorizer public key") from exc
    except ValueError as exc:
        raise SignatureError(f"invalid public key: {exc}") from exc


def fingerprint(pubkey_b64: str) -> str:
    """A stable, short fingerprint of a public key (sha256 of raw bytes, hex, truncated)."""
    try:
        raw = base64.b64decode(pubkey_b64)
    except (ValueError, TypeError):
        return ""
    return hashlib.sha256(raw).hexdigest()[:32]
