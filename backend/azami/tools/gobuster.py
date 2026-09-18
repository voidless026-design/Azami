"""Gobuster wrapper: content/DNS discovery on in-scope web services."""
from __future__ import annotations

import re

from azami.config import get_settings
from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper
from azami.wordlists import manager as wordlists

_URL_RE = re.compile(r"^https?://[A-Za-z0-9_.:\-/]+$")
_HOST_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


class GobusterWrapper(ToolWrapper):
    name = "gobuster"
    required_action = Action.ACTIVE_SCAN
    image = "azami/gobuster:latest"
    default_timeout = 900

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        settings = get_settings()
        mode = params.get("mode", "dir")
        wl_name = params.get("wordlist")
        if not wl_name:
            raise ToolParamError("a 'wordlist' name is required")
        if not wordlists.is_installed(wl_name):
            raise ToolParamError(f"wordlist '{wl_name}' is not installed; install it first")
        wl_path = str(wordlists.resolve_path(wl_name))

        threads = int(params.get("threads", 10))
        if not 1 <= threads <= 50:
            raise ToolParamError("threads must be 1..50")

        if mode == "dir":
            if not _URL_RE.match(target):
                raise ToolParamError("dir mode requires an http(s):// URL target")
            argv = ["gobuster", "dir", "-u", target, "-w", wl_path, "-q", "-t", str(threads)]
        elif mode == "dns":
            if not _HOST_RE.match(target):
                raise ToolParamError("dns mode requires a domain target")
            argv = ["gobuster", "dns", "-d", target, "-w", wl_path, "-q", "-t", str(threads)]
        else:
            raise ToolParamError("mode must be 'dir' or 'dns'")

        return ToolPlan(
            tool=self.name,
            target=target,
            argv=argv,
            required_action=self.required_action,
            image=self.image,
            timeout=self.default_timeout,
            read_only_mounts={str(settings.wordlists_dir): str(settings.wordlists_dir)},
        )

    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        found: list[str] = []
        findings: list[dict] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            found.append(line)
            findings.append(
                {
                    "title": f"Discovered: {line.split()[0]}",
                    "severity": "info",
                    "description": line,
                    "evidence": {"raw": line},
                }
            )
        return {"found": found, "count": len(found)}, findings
