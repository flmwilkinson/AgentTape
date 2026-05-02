"""Per-agent recompute debouncer.

Each agent recomputes at most once per ``recompute_debounce_seconds``,
even if 50 signals change in that window. The implementation is a
single-process in-memory map of ``agent_id -> last_recomputed_at`` plus
a ``dirty`` set. The subscriber adds to ``dirty`` on every event; a
background ticker periodically pops everything in ``dirty`` whose
last_recomputed_at is older than the debounce window and runs a single
batch through ``recompute_agents``.

The whole thing is one event loop, no locks needed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from scoring.compute import recompute_agents
from scoring.config import Settings, get_settings
from scoring.db import session_factory

log = logging.getLogger(__name__)


class Debouncer:
    """Coalesces recompute requests and flushes them on a tick."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._dirty: set[UUID] = set()
        self._last_compute: dict[UUID, float] = {}
        self._stop = asyncio.Event()

    def mark_dirty(self, agent_id: UUID) -> None:
        self._dirty.add(agent_id)

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self, redis_client: Any) -> None:
        """Loop forever flushing dirty agents on the debounce cadence."""
        log.info("debouncer running (window=%ds)", self.settings.recompute_debounce_seconds)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._tick_interval(),
                )
            except asyncio.TimeoutError:
                pass
            await self.flush(redis_client)

    def _tick_interval(self) -> float:
        # Wake every ~1/3 of the debounce window so flushes feel responsive
        # without slamming the loop.
        return max(5.0, self.settings.recompute_debounce_seconds / 3.0)

    async def flush(self, redis_client: Any) -> dict[str, int]:
        if not self._dirty:
            return {"recomputed": 0}
        now = time.monotonic()
        window = self.settings.recompute_debounce_seconds
        ready = {
            aid for aid in self._dirty
            if now - self._last_compute.get(aid, 0.0) >= window
        }
        if not ready:
            return {"recomputed": 0}

        self._dirty -= ready
        for aid in ready:
            self._last_compute[aid] = now

        async with session_factory()() as session:
            return await recompute_agents(session, ready, redis_client, self.settings)


# Module-level singleton — the subscriber and any sidecar share state.
_debouncer: Debouncer | None = None


def get_debouncer() -> Debouncer:
    global _debouncer
    if _debouncer is None:
        _debouncer = Debouncer()
    return _debouncer
