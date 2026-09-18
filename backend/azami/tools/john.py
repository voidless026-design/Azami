"""John the Ripper wrapper: offline cracking of hashes obtained lawfully within the engagement.

Gated at active_testing. Hash inputs MUST live in the engagement evidence store — no external
hash sources. The scope target is the in-scope asset the hashes belong to.
"""
from __future__ import annotations

import re

from azami.config import get_settings
from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper
from azami.wordlists import manager as wordlists

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_HOST_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


class JohnWrapper(ToolWrapper):
    name = "john"
    required_action = Action.ACTIVE_TESTING
    image = "azami/john:latest"
    default_timeout = 1800

    def _evidence_path(self, ref: str):
        settings = get_settings()
        if not _NAME_RE.match(ref):
            raise ToolParamError("invalid hash_ref")
        evidence_dir = (settings.data_dir / "evidence").resolve()
        path = (evidence_dir / ref).resolve()
        if not str(path).startswith(str(evidence_dir)):
            raise ToolParamError("hash_ref escapes the evidence store")
        if not path.exists():
            raise ToolParamError(f"hash file '{ref}' not found in the engagement evidence store")
        return path, evidence_dir

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        settings = get_settings()
        if not _HOST_RE.match(target):
            raise ToolParamError("invalid target (the in-scope asset the hashes belong to)")
        hash_ref = params.get("hash_ref")
        if not hash_ref:
            raise ToolParamError("a 'hash_ref' (file in the evidence store) is required")
        hash_path, evidence_dir = self._evidence_path(hash_ref)

        wl_name = params.get("wordlist")
        if not wl_name or not wordlists.is_installed(wl_name):
            raise ToolParamError("an installed 'wordlist' name is required")
        wl_path = wordlists.resolve_path(wl_name)

        argv = ["john", f"--wordlist={wl_path}", str(hash_path)]
        fmt = params.get("format")
        if fmt:
            if not re.match(r"^[A-Za-z0-9\-]+$", fmt):
                raise ToolParamError("invalid format")
            argv.insert(1, f"--format={fmt}")

        return ToolPlan(
            tool=self.name,
            target=target,
            argv=argv,
            required_action=self.required_action,
            image=self.image,
            timeout=self.default_timeout,
            read_only_mounts={
                str(settings.wordlists_dir): str(settings.wordlists_dir),
                str(evidence_dir): str(evidence_dir),
            },
        )

    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        combined = f"{stdout}\n{stderr}"
        cracked = 0
        m = re.search(r"(\d+)\s+password hash(?:es)? cracked", combined)
        if m:
            cracked = int(m.group(1))
        findings = []
        if cracked:
            findings.append(
                {
                    "title": f"{cracked} password hash(es) cracked",
                    "severity": "high",
                    "description": "Hashes from the evidence store were recovered with the wordlist.",
                    "evidence": {"cracked": cracked},
                }
            )
        return {"cracked": cracked, "raw": combined[:5000]}, findings
