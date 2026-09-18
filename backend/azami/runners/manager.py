"""Select the runner backend from config."""
from __future__ import annotations

from azami.config import get_settings
from azami.runners.base import Runner
from azami.runners.docker import DockerRunner
from azami.runners.local import LocalSubprocessRunner

_runner: Runner | None = None


def get_runner() -> Runner:
    global _runner
    if _runner is not None:
        return _runner
    backend = get_settings().runner_backend
    if backend == "docker":
        _runner = DockerRunner()
    elif backend == "remote":
        # RemoteRunner would submit to settings.remote_runner_url; falls back to local for dev.
        _runner = LocalSubprocessRunner()
    else:
        _runner = LocalSubprocessRunner()
    return _runner


def set_runner(runner: Runner) -> None:
    """Override the runner (used by tests)."""
    global _runner
    _runner = runner
