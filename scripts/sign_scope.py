#!/usr/bin/env python3
"""Generate an ed25519 keypair and/or sign an Azami scope file (azami-ed25519 scheme).

Usage:
  # 1. Generate an authorizer keypair (keep the private key safe/offline):
  python scripts/sign_scope.py keygen --out-dir ./keys

  # 2. Put the printed public key into the scope file's integrity.authorizer_pubkey,
  #    then sign the (final) scope file:
  python scripts/sign_scope.py sign --scope examples/scope.example.yaml \
      --private-key ./keys/authorizer.key

This prints the base64 signature and writes <scope>.sig next to it. Load it in Azami by
sending scope_text + signature_b64 to /api/engagement/load.
"""
from __future__ import annotations

import argparse
import base64
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def keygen(out_dir: str) -> None:
    d = pathlib.Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    (d / "authorizer.key").write_bytes(base64.b64encode(priv_raw))
    (d / "authorizer.pub").write_bytes(base64.b64encode(pub_raw))
    print(f"private key -> {d / 'authorizer.key'} (KEEP SECRET)")
    print(f"public key  -> {d / 'authorizer.pub'}")
    print("\nPut this into scope integrity.authorizer_pubkey:")
    print(base64.b64encode(pub_raw).decode())


def sign(scope_path: str, private_key_path: str) -> None:
    priv_b64 = pathlib.Path(private_key_path).read_bytes()
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(priv_b64))
    scope_bytes = pathlib.Path(scope_path).read_bytes()
    sig = base64.b64encode(priv.sign(scope_bytes)).decode()
    sig_path = pathlib.Path(scope_path + ".sig")
    sig_path.write_text(sig)
    print(f"signature -> {sig_path}")
    print(sig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("keygen")
    g.add_argument("--out-dir", default="./keys")
    s = sub.add_parser("sign")
    s.add_argument("--scope", required=True)
    s.add_argument("--private-key", required=True)
    args = p.parse_args()
    if args.cmd == "keygen":
        keygen(args.out_dir)
    elif args.cmd == "sign":
        sign(args.scope, args.private_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
