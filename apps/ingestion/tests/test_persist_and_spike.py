"""Persist + spike detection.

Drives the Ingestor base class with a hand-rolled subclass that returns
canned readings, against a real Postgres. Asserts:

- the first reading writes a signal but doesn't claim a spike
- a value change publishes a tick
- a >=2x value triggers signal_spike (events row + Redis publish)
- 2x of zero is not treated as a spike
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from sqlalchemy import text

from ingestion.config import Settings
from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("_reset_data")]


class _CannedIngestor(Ingestor):
    name: ClassVar[str] = "_canned"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_STARS
    tier: ClassVar[str] = "fast"

    def __init__(self, settings: Settings, readings: list[SignalReading]):
        super().__init__(settings)
        self._readings = readings

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        return self._readings


async def _make_agent(session) -> uuid.UUID:
    aid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, discovered_via, eligibility_status)
            VALUES (:id, :slug, :name, 'github_search', 'admitted')
            """
        ),
        {"id": aid, "slug": f"a-{aid.hex[:6]}", "name": "agent"},
    )
    await session.commit()
    return aid


async def _signals(session, agent_id, source: SignalSource) -> list[float]:
    rows = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid AND source = CAST(:src AS signal_source)
            ORDER BY captured_at ASC
            """
        ),
        {"aid": agent_id, "src": source.value},
    )
    return [float(r[0]) for r in rows]


async def _events(session, agent_id, kind: str) -> int:
    return (
        await session.execute(
            text(
                "SELECT count(*) FROM events "
                "WHERE agent_id = :id AND kind = CAST(:k AS event_kind)"
            ),
            {"id": agent_id, "k": kind},
        )
    ).scalar_one()


def _channels_published(redis_client) -> list[str]:
    return [c for c, _ in redis_client.published]


def _payloads_for(redis_client, channel: str) -> list[dict]:
    return [
        json.loads(msg) for c, msg in redis_client.published if c == channel
    ]


async def test_first_reading_writes_signal_no_spike(
    session, settings_with_db, redis_client
):
    aid = await _make_agent(session)
    now = datetime.now(UTC)
    ing = _CannedIngestor(
        settings_with_db,
        [SignalReading(aid, SignalSource.GITHUB_STARS, 100.0, now)],
    )
    try:
        stats = await ing.run(session, [], redis_client)
    finally:
        await ing.aclose()

    assert stats == {"fetched": 1, "written": 1, "spiked": 0, "changed": 0}
    assert await _signals(session, aid, SignalSource.GITHUB_STARS) == [100.0]
    assert await _events(session, aid, "signal_spike") == 0
    # Publish recorded as initial on the global event channel.
    payloads = _payloads_for(redis_client, "events.global")
    assert any(p.get("tick") == "initial" for p in payloads)


async def test_change_publishes_tick_no_spike(
    session, settings_with_db, redis_client
):
    aid = await _make_agent(session)
    now = datetime.now(UTC)
    ing = _CannedIngestor(
        settings_with_db,
        [SignalReading(aid, SignalSource.GITHUB_STARS, 100.0, now)],
    )
    try:
        await ing.run(session, [], redis_client)
        ing._readings = [
            SignalReading(
                aid,
                SignalSource.GITHUB_STARS,
                150.0,
                now + timedelta(minutes=5),
            )
        ]
        stats = await ing.run(session, [], redis_client)
    finally:
        await ing.aclose()

    assert stats["changed"] == 1
    assert stats["spiked"] == 0
    payloads = _payloads_for(redis_client, "events.global")
    assert any(p.get("tick") == "change" for p in payloads)


async def test_2x_jump_emits_signal_spike(
    session, settings_with_db, redis_client
):
    aid = await _make_agent(session)
    now = datetime.now(UTC)
    ing = _CannedIngestor(
        settings_with_db,
        [SignalReading(aid, SignalSource.GITHUB_STARS, 50.0, now)],
    )
    try:
        await ing.run(session, [], redis_client)
        ing._readings = [
            SignalReading(
                aid,
                SignalSource.GITHUB_STARS,
                200.0,  # 4x
                now + timedelta(minutes=5),
            )
        ]
        stats = await ing.run(session, [], redis_client)
    finally:
        await ing.aclose()

    assert stats["spiked"] == 1
    assert await _events(session, aid, "signal_spike") == 1
    spikes = [
        p for p in _payloads_for(redis_client, "events.global")
        if p.get("kind") == "signal_spike"
    ]
    assert spikes
    assert spikes[-1]["multiplier"] == 4.0


async def test_zero_to_one_is_not_a_spike(
    session, settings_with_db, redis_client
):
    """The 0 -> 1 case: no real signal yet, never claim a spike."""
    aid = await _make_agent(session)
    now = datetime.now(UTC)
    ing = _CannedIngestor(
        settings_with_db,
        [SignalReading(aid, SignalSource.GITHUB_STARS, 0.0, now)],
    )
    try:
        await ing.run(session, [], redis_client)
        ing._readings = [
            SignalReading(
                aid,
                SignalSource.GITHUB_STARS,
                1.0,  # would be infinite multiplier from 0
                now + timedelta(minutes=5),
            )
        ]
        stats = await ing.run(session, [], redis_client)
    finally:
        await ing.aclose()

    assert stats["spiked"] == 0
    assert await _events(session, aid, "signal_spike") == 0
