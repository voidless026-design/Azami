"""Nmap wrapper: port/service discovery on in-scope hosts. Reference implementation."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from azami.runners.base import ToolPlan
from azami.scope.schema import Action
from azami.tools.base import ToolParamError, ToolWrapper

_SCAN_TYPES = {
    "connect": ["-sT"],
    "syn": ["-sS"],
    "version": ["-sT", "-sV"],
    "ping": ["-sn"],
}
_PORTS_RE = re.compile(r"^[0-9]{1,5}(-[0-9]{1,5})?(,[0-9]{1,5}(-[0-9]{1,5})?)*$")
_TOPPORTS_RE = re.compile(r"^top(\d{1,5})$")
_HOST_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")  # exec uses argv, but reject obvious junk early


class NmapWrapper(ToolWrapper):
    name = "nmap"
    required_action = Action.ACTIVE_SCAN
    image = "instrumentisto/nmap:latest"
    default_timeout = 900

    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        if not _HOST_RE.match(target.strip()):
            raise ToolParamError("invalid target")

        scan_type = params.get("scan_type", "version")
        if scan_type not in _SCAN_TYPES:
            raise ToolParamError(f"scan_type must be one of {sorted(_SCAN_TYPES)}")
        argv = ["nmap", *_SCAN_TYPES[scan_type]]

        ports = str(params.get("ports", "top1000")).strip()
        top = _TOPPORTS_RE.match(ports)
        if top:
            n = int(top.group(1))
            if not 1 <= n <= 65535:
                raise ToolParamError("top-ports count out of range")
            argv += ["--top-ports", str(n)]
        elif scan_type != "ping":
            if not _PORTS_RE.match(ports):
                raise ToolParamError("ports must be like '80,443' or '1-1024' or 'top1000'")
            argv += ["-p", ports]

        timing = int(params.get("timing", 3))
        if not 0 <= timing <= 5:
            raise ToolParamError("timing must be 0..5")
        argv += [f"-T{timing}"]

        # Honor the scope's scan-rate cap.
        max_rate = constraints.get("max_scan_rate_pps")
        if max_rate:
            argv += ["--max-rate", str(int(max_rate))]

        argv += ["-oX", "-", target]  # XML to stdout for robust parsing
        return ToolPlan(
            tool=self.name,
            target=target,
            argv=argv,
            required_action=self.required_action,
            image=self.image,
            timeout=self.default_timeout,
        )

    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        try:
            root = ET.fromstring(stdout)
        except ET.ParseError:
            return {"raw": stdout[:5000], "parse_error": True}, []

        hosts: list[dict] = []
        findings: list[dict] = []
        for host in root.findall("host"):
            addr_el = host.find("address")
            addr = addr_el.get("addr") if addr_el is not None else "?"
            status_el = host.find("status")
            status = status_el.get("state") if status_el is not None else "unknown"
            ports = []
            for port in host.findall("./ports/port"):
                state_el = port.find("state")
                if state_el is None or state_el.get("state") != "open":
                    continue
                svc = port.find("service")
                entry = {
                    "port": int(port.get("portid")),
                    "protocol": port.get("protocol"),
                    "service": svc.get("name") if svc is not None else None,
                    "product": svc.get("product") if svc is not None else None,
                    "version": svc.get("version") if svc is not None else None,
                }
                ports.append(entry)
                findings.append(
                    {
                        "title": f"Open port {entry['port']}/{entry['protocol']} on {addr}",
                        "severity": "info",
                        "description": f"{entry.get('service') or 'unknown service'} "
                        f"{entry.get('product') or ''} {entry.get('version') or ''}".strip(),
                        "evidence": entry,
                    }
                )
            hosts.append({"address": addr, "status": status, "ports": ports})
        return {"hosts": hosts, "open_ports": sum(len(h["ports"]) for h in hosts)}, findings
