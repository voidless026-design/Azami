"""tcpdump wrapper: capture on an interface the engagement is authorized to monitor.

Gated at active_testing. The interface MUST appear in the scope's authorized capture-interface
list (constraints.tool_limits.tcpdump.interfaces) — never an ad-hoc capture aimed at a third party.
"""
from __future__ import annotations

import re

from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper

_IFACE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_BPF_RE = re.compile(r"^[A-Za-z0-9_.\-\s:/()\[\]<>=!&|]+$")  # conservative BPF charset
_HOST_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


class TcpdumpWrapper(ToolWrapper):
    name = "tcpdump"
    required_action = Action.ACTIVE_TESTING
    image = "azami/tcpdump:latest"
    default_timeout = 300

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        if not _HOST_RE.match(target):
            raise ToolParamError("invalid target (the in-scope segment/asset being monitored)")

        authorized = (constraints.get("tool_limits") or {}).get("tcpdump", {}).get("interfaces", [])
        iface = params.get("interface")
        if not iface or not _IFACE_RE.match(iface):
            raise ToolParamError("a valid 'interface' is required")
        if iface not in authorized:
            raise ToolParamError(
                "interface is not in the scope's authorized capture-interface list"
            )

        count = int(params.get("count", 200))
        if not 1 <= count <= 100000:
            raise ToolParamError("count must be 1..100000")

        argv = ["tcpdump", "-i", iface, "-nn", "-c", str(count)]
        bpf = params.get("filter")
        if bpf:
            if not _BPF_RE.match(bpf):
                raise ToolParamError("invalid BPF filter")
            argv += bpf.split()

        return ToolPlan(
            tool=self.name,
            target=target,
            argv=argv,
            required_action=self.required_action,
            image=self.image,
            timeout=int(params.get("duration", self.default_timeout)),
        )

    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        return {"packets_captured": len(lines), "sample": lines[:50]}, []
