"""Docker runner: each tool runs in a pinned, locked-down container.

Containers run non-root, with dropped capabilities, a read-only rootfs, resource caps, and
only the wordlist mounts the plan declares (read-only). This is the recommended production runner.
"""
from __future__ import annotations

import asyncio
import shutil

from azami.runners.base import EventCallback, Runner, RunResult, ToolPlan, ToolUnavailable


class DockerRunner(Runner):
    name = "docker"

    def __init__(self, cpus: str = "1.0", memory: str = "1g") -> None:
        self.cpus = cpus
        self.memory = memory

    def _docker_argv(self, plan: ToolPlan) -> list[str]:
        if not plan.image:
            raise ToolUnavailable(f"tool '{plan.tool}' has no docker image configured")
        argv = [
            "docker", "run", "--rm",
            "--user", "1000:1000",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--cpus", self.cpus,
            "--memory", self.memory,
            "--pids-limit", "256",
        ]
        for host_path, container_path in plan.read_only_mounts.items():
            argv += ["-v", f"{host_path}:{container_path}:ro"]
        # Pin the entrypoint to the tool binary so this works whatever the base
        # image's default entrypoint is; pass the remaining args as the command.
        argv += ["--entrypoint", plan.argv[0], plan.image, *plan.argv[1:]]
        return argv

    async def run(self, plan: ToolPlan, on_event: EventCallback) -> RunResult:
        if shutil.which("docker") is None:
            raise ToolUnavailable("docker is not available on this host")
        argv = self._docker_argv(plan)
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out: list[str] = []
        err: list[str] = []

        async def pump(stream, kind, sink):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                sink.append(text)
                on_event(kind, text)

        try:
            await asyncio.wait_for(
                asyncio.gather(pump(proc.stdout, "stdout", out), pump(proc.stderr, "stderr", err)),
                timeout=plan.timeout,
            )
            await asyncio.wait_for(proc.wait(), timeout=plan.timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            raise
        return RunResult(proc.returncode or -1, "\n".join(out), "\n".join(err))
