"""Tool wrapper interface. Wrappers build validated argument arrays (never shell strings)
and parse tool output into a structured result + findings."""
from __future__ import annotations

from abc import ABC, abstractmethod

from azami.runners.base import ToolPlan
from azami.scope.schema import Action


class ToolParamError(Exception):
    """Raised when tool parameters fail validation (surfaced as HTTP 422)."""


class ToolWrapper(ABC):
    name: str = "base"
    required_action: Action = Action.ACTIVE_SCAN
    image: str | None = None
    default_timeout: int = 300

    @abstractmethod
    def plan(self, target: str, params: dict, constraints: dict) -> ToolPlan:
        """Validate params + scope constraints and return an executable ToolPlan."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, stdout: str, stderr: str, exit_code: int) -> tuple[dict, list[dict]]:
        """Return (structured_result, findings). findings: list of
        {title, severity, description, evidence}."""
        raise NotImplementedError
