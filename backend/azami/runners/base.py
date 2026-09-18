"""Runner abstraction + tool-job types + job state machine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from azami.scope.schema import Action


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


TERMINAL_STATES = {
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.CANCELLED,
    JobState.TIMED_OUT,
}


class ToolUnavailable(Exception):
    """The tool binary / image / remote runner is not available."""


@dataclass
class ToolPlan:
    """A validated, ready-to-execute tool invocation produced by a ToolWrapper."""

    tool: str
    target: str
    argv: list[str]  # command + args (run directly locally; inside the image for docker)
    required_action: Action
    image: str | None = None
    timeout: int = 300
    read_only_mounts: dict[str, str] = field(default_factory=dict)  # host_path -> container_path


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str


# on_event(event_type, text) — called for each stdout/stderr line during a run.
EventCallback = Callable[[str, str], None]


@dataclass
class JobEvent:
    job_id: str
    type: str  # "state" | "stdout" | "stderr" | "result" | "error"
    data: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {"job_id": self.job_id, "type": self.type, "data": self.data, "ts": self.ts}


class Runner(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, plan: ToolPlan, on_event: EventCallback) -> RunResult:
        """Execute the plan, streaming lines via on_event. Raise ToolUnavailable if it can't run."""
        raise NotImplementedError
