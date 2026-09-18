"""Hydra wrapper: credential-strength testing against in-scope, authorized services.

Gated at active_testing and additionally requires per-run confirmation (enforced by the job
service). Runs gently (low thread count, stop-on-first) and lockout-aware where the scope says so.
"""
from __future__ import annotations

import re

from azami.config import get_settings
from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper
from azami.wordlists import manager as wordlists

# A conservative service allow-list.
_SERVICES = {"ssh", "ftp", "smtp", "pop3", "imap", "rdp", "smb", "http-get", "https-get"}
_HOST_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


class HydraWrapper(ToolWrapper):
    name = "hydra"
    required_action = Action.ACTIVE_TESTING
    image = "azami/hydra:latest"
    default_timeout = 1800

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        settings = get_settings()
        if not _HOST_RE.match(target):
            raise ToolParamError("invalid target host")
        service = params.get("service")
        if service not in _SERVICES:
            raise ToolParamError(f"service must be one of {sorted(_SERVICES)}")

        userlist = params.get("userlist")
        passlist = params.get("passlist")
        for label, name in (("userlist", userlist), ("passlist", passlist)):
            if not name:
                raise ToolParamError(f"a '{label}' wordlist name is required")
            if not wordlists.is_installed(name):
                raise ToolParamError(f"wordlist '{name}' is not installed; install it first")

        # Honor scope-configured hydra limits.
        hydra_limits = (constraints.get("tool_limits") or {}).get("hydra", {})
        max_threads = int(params.get("threads", hydra_limits.get("max_threads", 4)))
        max_threads = max(1, min(max_threads, hydra_limits.get("max_threads", 8)))

        argv = [
            "hydra",
            "-L", str(wordlists.resolve_path(userlist)),
            "-P", str(wordlists.resolve_path(passlist)),
            "-t", str(max_threads),
            "-f",  # stop after the first valid pair found
            target,
            service,
        ]
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
        creds: list[dict] = []
        findings: list[dict] = []
        for line in stdout.splitlines():
            m = re.search(r"login:\s*(\S+)\s+password:\s*(\S+)", line)
            if m:
                entry = {"login": m.group(1), "password_found": True, "password": m.group(2)}
                creds.append(entry)
                findings.append(
                    {
                        "title": f"Weak credential accepted for {entry['login']}",
                        "severity": "high",
                        "description": "Service accepted a credential from the test list.",
                        "evidence": entry,
                    }
                )
        return {"credentials_found": creds, "count": len(creds)}, findings
