"""In-process async event bus for streaming job events to WebSocket clients."""
from __future__ import annotations

import asyncio


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(job_id)
        if subs and q in subs:
            subs.remove(q)
        if subs is not None and not subs:
            self._subs.pop(job_id, None)

    def publish(self, job_id: str, event: dict) -> None:
        for q in list(self._subs.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover
                pass


bus = EventBus()
