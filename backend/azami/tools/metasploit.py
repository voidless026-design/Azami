"""Metasploit wrapper: verify specific findings via authorized modules on in-scope hosts.

Gated at exploitation + per-run confirmation. Defaults to auxiliary/scanner modules; anything
beyond the safe prefixes must be explicitly named and is still confined to in-scope targets.
"""
from __future__ import annotations

import re

from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper

_MODULE_RE = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)+$")
_HOST_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")
# Safe-by-default module prefixes (non-payload). Others require exploitation grant + confirm.
_SAFE_PREFIXES = ("auxiliary/scanner/", "auxiliary/gather/", "post/")


class MetasploitWrapper(ToolWrapper):
    name = "metasploit"
    required_action = Action.EXPLOITATION
    image = "azami/metasploit:latest"
    default_timeout = 1200

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        if not _HOST_RE.match(target):
            raise ToolParamError("invalid target host")
        module = params.get("module", "auxiliary/scanner/portscan/tcp")
        if not _MODULE_RE.match(module):
            raise ToolParamError("invalid module path")

        allow_exploit = bool(params.get("allow_exploit", False))
        if not module.startswith(_SAFE_PREFIXES) and not allow_exploit:
            raise ToolParamError(
                "non-scanner module requires allow_exploit=true (and an exploitation-granted scope)"
            )

        # Build a single msf command string; runs via exec (no shell), target is charset-validated.
        options = params.get("options", {})
        set_cmds = [f"set RHOSTS {target}"]
        for k, v in options.items():
            if not re.match(r"^[A-Za-z0-9_]+$", str(k)) or not re.match(r"^[A-Za-z0-9_.:\-/]+$", str(v)):
                raise ToolParamError(f"invalid module option {k}={v}")
            set_cmds.append(f"set {k} {v}")
        resource = f"use {module}; " + "; ".join(set_cmds) + "; run; exit"

        argv = ["msfconsole", "-q", "-x", resource]
        return ToolPlan(
            tool=self.name,
            target=target,
            argv=argv,
            required_action=self.required_action,
            image=self.image,
            timeout=self.default_timeout,
        )

    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        findings = []
        for line in stdout.splitlines():
            if "[+]" in line:  # msf convention for a positive result
                findings.append(
                    {
                        "title": "Metasploit positive result",
                        "severity": "medium",
                        "description": line.strip(),
                        "evidence": {"raw": line.strip()},
                    }
                )
        return {"raw": stdout[:8000], "positives": len(findings)}, findings
