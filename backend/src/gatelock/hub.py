"""In-process fan-out of live events to dashboard WebSocket clients."""

import asyncio
from typing import Any

Message = tuple[str, Any]


class Hub:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict]] = set()

    def subscribe(self) -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict]) -> None:
        self._queues.discard(q)

    def publish(self, messages: list[Message]) -> None:
        for kind, data in messages:
            for q in self._queues:
                try:
                    q.put_nowait({"type": kind, "data": data})
                except asyncio.QueueFull:
                    pass  # slow client; it will resync from the REST API


hub = Hub()
