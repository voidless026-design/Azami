"""Nmap wrapper: argv construction + validation + XML parsing (offline unit tests)."""
from __future__ import annotations

import pytest

from azami.tools.base import ToolParamError
from azami.tools.nmap import NmapWrapper

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
 <host>
  <status state="up"/>
  <address addr="203.0.113.10" addrtype="ipv4"/>
  <ports>
   <port protocol="tcp" portid="22"><state state="open"/>
     <service name="ssh" product="OpenSSH" version="8.2"/></port>
   <port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port>
   <port protocol="tcp" portid="443"><state state="closed"/></port>
  </ports>
 </host>
</nmaprun>"""


@pytest.fixture
def nmap():
    return NmapWrapper()


def test_plan_defaults(nmap):
    plan = nmap.plan("example.com", {}, {})
    assert plan.argv[:3] == ["nmap", "-sT", "-sV"]
    assert "--top-ports" in plan.argv and "1000" in plan.argv
    assert plan.argv[-3:] == ["-oX", "-", "example.com"]


def test_plan_explicit_ports_and_rate(nmap):
    plan = nmap.plan(
        "example.com", {"ports": "80,443", "scan_type": "connect"}, {"max_scan_rate_pps": 500}
    )
    assert "-p" in plan.argv and "80,443" in plan.argv
    assert plan.argv[1] == "-sT"
    i = plan.argv.index("--max-rate")
    assert plan.argv[i + 1] == "500"


def test_plan_rejects_bad_params(nmap):
    with pytest.raises(ToolParamError):
        nmap.plan("example.com", {"scan_type": "nuke"}, {})
    with pytest.raises(ToolParamError):
        nmap.plan("example.com", {"ports": "not-ports"}, {})
    with pytest.raises(ToolParamError):
        nmap.plan("bad target with spaces", {}, {})


def test_parse_extracts_open_ports(nmap):
    result, findings = nmap.parse(SAMPLE_XML, "", 0)
    assert result["open_ports"] == 2
    ports = {p["port"] for p in result["hosts"][0]["ports"]}
    assert ports == {22, 80}
    assert len(findings) == 2
    ssh = next(p for p in result["hosts"][0]["ports"] if p["port"] == 22)
    assert ssh["product"] == "OpenSSH" and ssh["version"] == "8.2"


def test_parse_handles_garbage(nmap):
    result, findings = nmap.parse("not xml", "", 0)
    assert result.get("parse_error") and findings == []
