"""Snapshot tests against real Postgres."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from realtime import snapshots

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("_reset_data")]


async def _make_agent(session, slug: str, *, score: float | None = None) -> uuid.UUID:
    aid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, discovered_via, eligibility_status)
            VALUES (:id, :slug, :name, 'github_search', 'admitted')
            """
        ),
        {"id": aid, "slug": slug, "name": slug},
    )
    if score is not None:
        await session.execute(
            text(
                """
                INSERT INTO scores (id, agent_id, computed_at, agent_score,
                                    adoption, quality, momentum, community,
                                    manipulation_resistance)
                VALUES (gen_random_uuid(), :id, now(), :s, :s, :s, :s, :s, 1.0)
                """
            ),
            {"id": aid, "s": score},
        )
    await session.commit()
    return aid


async def test_ticker_snapshot_returns_recent_events(session, settings_with_db):
    aid = await _make_agent(session, "ticker-agent")
    for i in range(3):
        await session.execute(
            text(
                """
                INSERT INTO events (id, kind, agent_id, payload)
                VALUES (gen_random_uuid(), CAST('signal_spike' AS event_kind),
                        :id, CAST(:p AS jsonb))
                """
            ),
            {"id": aid, "p": json.dumps({"i": i})},
        )
    await session.commit()

    snap = await snapshots.ticker_snapshot(session, limit=10)
    assert snap["type"] == "snapshot"
    assert snap["scope"] == "ticker"
    assert len(snap["events"]) >= 3


async def test_agent_snapshot_carries_score_envelope(session, settings_with_db):
    await _make_agent(session, "snap-agent", score=72.5)
    snap = await snapshots.agent_snapshot(session, "snap-agent")
    assert snap is not None
    assert snap["agent"]["slug"] == "snap-agent"
    score = snap["score"]
    expected_keys = {
        "agent_score",
        "adoption",
        "quality",
        "momentum",
        "community",
        "manipulation_resistance",
        "computed_at",
    }
    assert set(score.keys()) == expected_keys
    assert score["agent_score"] == 72.5


async def test_agent_snapshot_returns_none_for_unknown(session, settings_with_db):
    assert await snapshots.agent_snapshot(session, "nope") is None


async def test_index_snapshot_includes_members(session, settings_with_db):
    aid = await _make_agent(session, "index-member", score=80.0)
    await session.execute(
        text(
            """
            INSERT INTO indexes (id, slug, name, methodology_md,
                                 rebalance_frequency, eligibility_rules)
            VALUES (gen_random_uuid(), 'tape-100', 'TAPE-100', 'methodology',
                    'weekly', CAST(:rules AS jsonb))
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {"rules": json.dumps({"top_n": 100})},
    )
    iid = (
        await session.execute(text("SELECT id FROM indexes WHERE slug='tape-100'"))
    ).scalar_one()
    await session.execute(
        text(
            """
            INSERT INTO index_members (index_id, agent_id, added_at, weight)
            VALUES (:iid, :aid, now(), 0.01)
            """
        ),
        {"iid": iid, "aid": aid},
    )
    await session.commit()

    snap = await snapshots.index_snapshot(session, "tape-100")
    assert snap is not None
    assert snap["index"]["slug"] == "tape-100"
    assert snap["index"]["members_count"] == 1
    assert snap["members"][0]["slug"] == "index-member"


async def test_watchlist_snapshot_filters_by_slug(session, settings_with_db):
    await _make_agent(session, "watch-a", score=10.0)
    await _make_agent(session, "watch-b", score=20.0)
    await _make_agent(session, "ignored", score=99.0)

    snap = await snapshots.watchlist_snapshot(session, ["watch-a", "watch-b"])
    slugs = {a["slug"] for a in snap["agents"]}
    assert slugs == {"watch-a", "watch-b"}
    # Each carries the strict envelope shape.
    expected_keys = {
        "agent_score",
        "adoption",
        "quality",
        "momentum",
        "community",
        "manipulation_resistance",
        "computed_at",
    }
    for a in snap["agents"]:
        assert set(a["score"].keys()) == expected_keys
