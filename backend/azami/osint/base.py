"""Collector interface and shared types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from azami.entities.canonical import EntityType
from azami.scope.schema import Action


@dataclass
class RawRecord:
    """One collector's normalized assertion about an entity."""

    entity_type: EntityType
    dedup_key: str
    fields: dict = field(default_factory=dict)
    field_values: dict | None = None  # per-field provenance values; defaults to `fields`


class Collector(ABC):
    name: str = "base"
    produces: list[EntityType] = []
    requires_action: Action = Action.PASSIVE
    applies_to: set[str] = set()  # target kinds: {"domain","ip","email"}
    enabled: bool = True

    @abstractmethod
    async def collect(self, value: str, kind: str) -> list[RawRecord]:
        """Collect for a target value already confirmed in-scope by the runner."""
        raise NotImplementedError
