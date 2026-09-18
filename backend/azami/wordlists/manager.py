"""Wordlist/dictionary manager: catalog, install (checksum-verified), resolve, version.

Lists are fetched only on explicit request, verified, versioned, and mounted read-only into
tool runners so runs are reproducible. Names are validated to prevent path traversal.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import httpx
import yaml

from azami.config import get_settings

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _catalog() -> list[dict]:
    settings = get_settings()
    if not settings.wordlist_catalog.exists():
        return []
    data = yaml.safe_load(settings.wordlist_catalog.read_text()) or {}
    return data.get("lists", [])


def catalog() -> list[dict]:
    return _catalog()


def resolve_path(name: str) -> Path:
    """Resolve a wordlist name to a path inside the managed dir; reject traversal."""
    if not _NAME_RE.match(name):
        raise ValueError(f"invalid wordlist name: {name!r}")
    settings = get_settings()
    path = (settings.wordlists_dir / f"{name}.txt").resolve()
    if not str(path).startswith(str(settings.wordlists_dir.resolve())):
        raise ValueError("wordlist path escapes managed directory")
    return path


def is_installed(name: str) -> bool:
    try:
        return resolve_path(name).exists()
    except ValueError:
        return False


def status() -> list[dict]:
    out = []
    for entry in _catalog():
        name = entry["name"]
        p = resolve_path(name) if _NAME_RE.match(name) else None
        out.append(
            {
                "name": name,
                "category": entry.get("category"),
                "license": entry.get("license"),
                "version": entry.get("version"),
                "installed": bool(p and p.exists()),
                "size_bytes": p.stat().st_size if p and p.exists() else 0,
            }
        )
    return out


def install(name: str) -> dict:
    """Download a cataloged wordlist, verify its checksum (if any), and store it."""
    entry = next((e for e in _catalog() if e["name"] == name), None)
    if entry is None:
        raise ValueError(f"unknown wordlist: {name}")
    dest = resolve_path(name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60.0, follow_redirects=True) as c:
        resp = c.get(entry["source_url"])
        resp.raise_for_status()
        content = resp.content
    expected = entry.get("checksum")
    actual = hashlib.sha256(content).hexdigest()
    if expected and expected != actual:
        raise ValueError(f"checksum mismatch for {name}: expected {expected}, got {actual}")
    dest.write_bytes(content)
    return {
        "name": name,
        "path": str(dest),
        "size_bytes": len(content),
        "sha256": actual,
        "version": entry.get("version"),
    }
