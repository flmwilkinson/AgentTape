"""Connection backpressure + heartbeat behavior.

These don't need Postgres or Redis — we drive the bounded queue
directly to assert the spec'd behavior:

- Drop oldest when full + emit a single warning frame
- Heartbeats fire when the queue is idle
"""
from __future__ import annotations

import asyncio

import pytest

from realtime.config import Settings
from realtime.connection import Connection

pytestmark = pytest.mark.asyncio


def _make(qsize: int = 4, heartbeat: float = 0.05) -> Connection:
    s = Settings(queue_size=qsize, heartbeat_seconds=heartbeat)
    return Connection([], settings=s)


async def test_push_under_capacity_passes_through():
    c = _make(qsize=4)
    for i in range(3):
        c.push({"type": "event", "i": i})
    out = []
    it = c.messages()
    for _ in range(3):
        out.append(await it.__anext__())
    assert [f["i"] for f in out] == [0, 1, 2]


async def test_overflow_drops_oldest_and_emits_one_warning():
    c = _make(qsize=4)
    for i in range(10):
        c.push({"type": "event", "i": i})
    received: list[dict] = []
    it = c.messages()
    # We pushed 10 into a queue of 4 — at most 4 frames will come out
    # before the next push, and the warning sits in the tail.
    while True:
        try:
            received.append(await asyncio.wait_for(it.__anext__(), timeout=0.2))
        except asyncio.TimeoutError:
            break
        if len(received) > 6:  # safety
            break

    warnings = [f for f in received if f.get("type") == "warning"]
    events = [f for f in received if f.get("type") == "event"]
    assert len(warnings) == 1
    # Oldest events were dropped — surviving events should be the highest indices.
    assert events
    surviving = [f["i"] for f in events]
    assert min(surviving) >= 6  # at least the last 4 of {6..9} survived


async def test_heartbeat_fires_on_idle():
    c = _make(qsize=4, heartbeat=0.05)
    it = c.messages()
    frame = await asyncio.wait_for(it.__anext__(), timeout=0.5)
    assert frame == {"type": "heartbeat"}


async def test_warning_resets_after_consumer_catches_up():
    """Once the queue empties, a fresh overflow triggers a fresh warning."""
    c = _make(qsize=2)
    for i in range(5):
        c.push({"type": "event", "i": i})
    seen = []
    it = c.messages()
    while True:
        try:
            seen.append(await asyncio.wait_for(it.__anext__(), timeout=0.2))
        except asyncio.TimeoutError:
            break
        if len(seen) > 5:
            break
    first_warnings = [f for f in seen if f.get("type") == "warning"]
    assert len(first_warnings) == 1

    # New burst — warning fires again.
    for i in range(5):
        c.push({"type": "event", "i": 100 + i})
    seen2 = []
    while True:
        try:
            seen2.append(await asyncio.wait_for(it.__anext__(), timeout=0.2))
        except asyncio.TimeoutError:
            break
        if len(seen2) > 5:
            break
    second_warnings = [f for f in seen2 if f.get("type") == "warning"]
    assert len(second_warnings) == 1
