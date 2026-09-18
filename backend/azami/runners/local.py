"""Local subprocess runner (development). Streams stdout/stderr line-by-line with a timeout."""
from __future__ import annotations

import asyncio

from azami.runners.base import EventCallback, RunResult, Runner, ToolPlan, ToolUnavailable


class LocalSubprocessRunner(Runner):
    name = "local"

    async def run(self, plan: ToolPlan, on_event: EventCallback) -> RunResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *plan.argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ToolUnavailable(
                f"'{plan.argv[0]}' is not installed on this host (runner_backend=local)"
            ) from exc

        out_chunks: list[str] = []
        err_chunks: list[str] = []

        async def pump(stream, kind: str, sink: list[str]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                sink.append(text)
                on_event(kind, text)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    pump(proc.stdout, "stdout", out_chunks),
                    pump(proc.stderr, "stderr", err_chunks),
                ),
                timeout=plan.timeout,
            )
            await asyncio.wait_for(proc.wait(), timeout=plan.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        except asyncio.CancelledError:
            proc.kill()
            raise

        return RunResult(
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout="\n".join(out_chunks),
            stderr="\n".join(err_chunks),
        )
