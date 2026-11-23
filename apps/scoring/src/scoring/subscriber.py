"""Redis pub/sub subscriber.

Listens on the global event channel and marks agents dirty in the
debouncer. The actual recompute runs on the debouncer's tick — never
on the subscriber thread — so a flood of ticks can never block
recompute work.

Channel: ``events.global`` (everything ingestion / discovery / scoring publishes).
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import redis.asyncio as redis_async

from scoring.config import Settings, get_settings
from scoring.debouncer import Debouncer

log = logging.getLogger(__name__)


CHANNELS = ("events.global",)


async def run_subscriber(
    debouncer: Debouncer, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    client = redis_async.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(*CHANNELS)
    log.info("subscriber listening on %s", ", ".join(CHANNELS))

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            _handle(debouncer, message.get("channel"), message.get("data"))
    finally:
        await pubsub.unsubscribe(*CHANNELS)
        await pubsub.aclose()
        await client.aclose()


def _handle(debouncer: Debouncer, channel: str, raw: Any) -> None:
    if not raw:
        return
    try:
        msg = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return

    aid_raw = msg.get("agent_id")
    if not aid_raw:
        return
    try:
        aid = uuid.UUID(aid_raw)
    except (TypeError, ValueError):
        return
    debouncer.mark_dirty(aid)
    # Don't log every event — channels are high-throughput. Only at debug.
    log.debug("dirty: %s via %s", aid, channel)
