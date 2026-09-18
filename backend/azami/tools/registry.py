"""Tool wrapper registry."""
from __future__ import annotations

from azami.tools.base import ToolWrapper

_REGISTRY: dict[str, ToolWrapper] = {}


def register(wrapper: ToolWrapper) -> None:
    _REGISTRY[wrapper.name] = wrapper


def get(name: str) -> ToolWrapper | None:
    return _REGISTRY.get(name)


def all_tools() -> list[ToolWrapper]:
    return list(_REGISTRY.values())


def _bootstrap() -> None:
    from azami.tools.gobuster import GobusterWrapper
    from azami.tools.hydra import HydraWrapper
    from azami.tools.john import JohnWrapper
    from azami.tools.metasploit import MetasploitWrapper
    from azami.tools.nmap import NmapWrapper
    from azami.tools.tcpdump import TcpdumpWrapper

    for cls in (
        NmapWrapper,
        GobusterWrapper,
        HydraWrapper,
        JohnWrapper,
        MetasploitWrapper,
        TcpdumpWrapper,
    ):
        register(cls())


_bootstrap()
