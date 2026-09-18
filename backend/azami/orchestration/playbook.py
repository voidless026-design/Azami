"""Playbook definitions: chained recon steps. Each derived target is re-gated at run time."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlaybookStep:
    id: str
    action: str  # "collect" | "tool"
    name: str  # collector name or tool name
    targets: str = "root"  # "root" | "ips" | "hosts"
    params: dict = field(default_factory=dict)


@dataclass
class Playbook:
    name: str
    description: str
    steps: list[PlaybookStep]


BUILTIN: dict[str, Playbook] = {
    "passive_footprint": Playbook(
        name="passive_footprint",
        description="Passive-only footprint of the root asset (DNS, RDAP, cert transparency).",
        steps=[
            PlaybookStep("dns", "collect", "dns", "root"),
            PlaybookStep("rdap", "collect", "rdap", "root"),
            PlaybookStep("crtsh", "collect", "crtsh", "root"),
        ],
    ),
    "attack_surface_map": Playbook(
        name="attack_surface_map",
        description="Passive discovery, then an active port scan of each discovered in-scope IP.",
        steps=[
            PlaybookStep("dns", "collect", "dns", "root"),
            PlaybookStep("crtsh", "collect", "crtsh", "root"),
            PlaybookStep("geoip", "collect", "geoip", "ips"),
            PlaybookStep(
                "portscan", "tool", "nmap", "ips",
                {"ports": "top1000", "scan_type": "version"},
            ),
        ],
    ),
    "web_content_discovery": Playbook(
        name="web_content_discovery",
        description="Directory brute-force of an in-scope web service (requires a wordlist).",
        steps=[
            PlaybookStep(
                "gobuster", "tool", "gobuster", "root",
                {"mode": "dir", "wordlist": "seclists-common-web-content"},
            ),
        ],
    ),
}
