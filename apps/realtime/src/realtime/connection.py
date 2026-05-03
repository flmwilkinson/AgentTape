"""Per-client connection abstraction.

Each WS / SSE handler builds a :class:`Connection` for the duration of
the request, hands it the list of Redis channels to listen on, and
loops on ``messages()`` to forward frames out to the client.

Backpressure: the queue is bounded. When full we drop the oldest
event and emit a single ``warning`` frame to the client so they know
they've fallen behind. Heartbeats fire every ``heartbeat_seconds``
even when there's no traffic so dead-link detection is fast.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis_async

from realtime.config import Settings, get_settings

log = logging.getLogger(__name__)


SENTINEL_HEARTBEAT = {"type": "heartbeat"}


class Connection:
    """Couples a Redis pub/sub subscription to a per-client bounded queue."""

    def __init__(
        self,
        channels: list[str],
        *,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.channels = channels
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.settings.queue_size
        )
        self._client: Any = None
        self._pubsub: Any = None
        self._task: asyncio.Task[None] | None = None
        # Pending warning lives outside the queue so a continuing flood can't
        # evict it. It clears the next time the consumer reads — after which
        # a new overflow burst sets it again.
        self._pending_warning = False
        self._closed = False

    async def start(self) -> None:
        self._client = redis_async.from_url(
            self.settings.redis_url, decode_responses=True
        )
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*self.channels)
        self._task = asyncio.create_task(self._pump())
        log.debug("connection subscribed to %s", self.channels)

    async def stop(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(*self.channels)
            except Exception:  # noqa: BLE001
                pass
            try:
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001
                pass

    def push(self, frame: dict[str, Any]) -> None:
        """Enqueue a frame from the application side (e.g. snapshots)."""
        self._enqueue(frame)

    def _enqueue(self, frame: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(frame)
            return
        except asyncio.QueueFull:
            pass
        # Drop oldest to make room for the new frame.
        try:
            _ = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Should be unreachable after the get_nowait above.
            pass
        # Mark warning pending; ``messages`` emits one warning frame
        # on the next consume before the next event.
        self._pending_warning = True

    async def _pump(self) -> None:
        """Forward Redis messages into the queue."""
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                if not raw:
                    continue
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, ValueError):
                    continue
                self._enqueue(
                    {
                        "type": "event",
                        "channel": message.get("channel"),
                        "event": payload,
                    }
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("redis pump failed")

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        """Yield frames forever — heartbeats fill the gaps."""
        hb = self.settings.heartbeat_seconds
        while not self._closed:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=hb)
                if self._pending_warning:
                    self._pending_warning = False
                    yield {
                        "type": "warning",
                        "reason": "slow_client",
                        "detail": "events dropped; you fell behind the queue",
                    }
                yield frame
            except asyncio.TimeoutError:
                yield SENTINEL_HEARTBEAT
