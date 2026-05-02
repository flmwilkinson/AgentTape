"""Schema integration tests.

These run against a real Postgres (pgvector/pgvector:pg16) spun up by
testcontainers. They verify that:

- Extensions, enums, and the current_scores view exist.
- ``signals`` is partitioned and rows route to the right monthly partition.
- ``current_scores`` returns exactly one row per agent — the latest — even
  with many score rows per agent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.asyncio


# -------------------------------------------------------------------- core


async def test_extensions_present(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto','vector')")
    )
    names = {row[0] for row in result.all()}
    assert names == {"pgcrypto", "vector"}


async def test_enums_have_expected_values(session: AsyncSession) -> None:
    result = await session.execute(
        text(
            """
            SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname IN (
                'discovery_via','eligibility_status','discovery_source',
                'tag_kind','signal_source','event_kind'
            )
            GROUP BY t.typname
            """
        )
    )
    enums = {name: list(values) for name, values in result.all()}
    assert "admitted" in enums["eligibility_status"]
    assert "github_stars" in enums["signal_source"]
    assert "agent_admitted" in enums["event_kind"]
    # Spot-check that every enum has at least the documented size.
    assert len(enums["signal_source"]) >= 16
    assert len(enums["discovery_via"]) == 7


# ------------------------------------------------------------- partitioning


async def test_signals_is_partitioned_by_captured_at(session: AsyncSession) -> None:
    result = await session.execute(
        text(
            """
            SELECT pg_get_partkeydef(c.oid)
            FROM pg_class c
            JOIN pg_partitioned_table p ON p.partrelid = c.oid
            WHERE c.relname = 'signals'
            """
        )
    )
    row = result.first()
    assert row is not None, "signals must be partitioned"
    assert "RANGE" in row[0].upper()
    assert "captured_at" in row[0]


async def test_signals_routes_rows_to_correct_monthly_partition(
    session: AsyncSession,
) -> None:
    """Insert across two adjacent months and verify each row lands in its own partition."""
    agent_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, discovered_via)
            VALUES (:id, :slug, :name, 'github_search')
            """
        ),
        {"id": agent_id, "slug": f"a-{agent_id.hex[:8]}", "name": "test-agent"},
    )

    # Use this month and next month — the migration pre-creates both.
    now = datetime.now(timezone.utc).replace(day=15, hour=12, minute=0, second=0, microsecond=0)
    next_month = (now.replace(day=1) + timedelta(days=40)).replace(day=15)

    for ts in (now, next_month):
        await session.execute(
            text(
                """
                INSERT INTO signals (id, captured_at, agent_id, source, value)
                VALUES (gen_random_uuid(), :ts, :agent_id, 'github_stars', 42)
                """
            ),
            {"ts": ts, "agent_id": agent_id},
        )
    await session.commit()

    # Each ts should appear in the partition matching its YYYYMM.
    for ts in (now, next_month):
        partition = f"signals_p{ts.strftime('%Y%m')}"
        result = await session.execute(
            text(f"SELECT count(*) FROM {partition} WHERE captured_at = :ts"),
            {"ts": ts},
        )
        count = result.scalar_one()
        assert count == 1, f"expected 1 row in {partition}, got {count}"

    # And they should not have leaked into the default partition.
    result = await session.execute(text("SELECT count(*) FROM signals_default"))
    assert result.scalar_one() == 0


async def test_partition_helper_creates_future_partition(
    session: AsyncSession,
) -> None:
    """The ingestion service calls agenttape_create_signals_partition ahead of each month."""
    far_future = datetime(2099, 7, 1, tzinfo=timezone.utc).date()
    await session.execute(
        text("SELECT agenttape_create_signals_partition(:d)"),
        {"d": far_future},
    )
    await session.commit()
    result = await session.execute(
        text(
            "SELECT 1 FROM pg_class WHERE relname = 'signals_p209907' "
            "AND relkind = 'r'"
        )
    )
    assert result.first() is not None


# ----------------------------------------------------------- current_scores


async def _insert_agent(session: AsyncSession, slug: str) -> uuid.UUID:
    agent_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO agents (id, slug, name, discovered_via) "
            "VALUES (:id, :slug, :name, 'github_search')"
        ),
        {"id": agent_id, "slug": slug, "name": slug},
    )
    return agent_id


async def _insert_score(
    session: AsyncSession,
    agent_id: uuid.UUID,
    computed_at: datetime,
    agent_score: float,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO scores (
                id, agent_id, computed_at,
                agent_score, adoption, quality, momentum, community,
                manipulation_resistance
            ) VALUES (
                gen_random_uuid(), :agent_id, :computed_at,
                :s, :s, :s, :s, :s, :s
            )
            """
        ),
        {"agent_id": agent_id, "computed_at": computed_at, "s": agent_score},
    )


async def test_current_scores_returns_latest_per_agent(session: AsyncSession) -> None:
    a = await _insert_agent(session, "agent-a")
    b = await _insert_agent(session, "agent-b")

    base = datetime.now(timezone.utc) - timedelta(hours=3)
    await _insert_score(session, a, base, 1.0)
    await _insert_score(session, a, base + timedelta(hours=1), 2.0)
    await _insert_score(session, a, base + timedelta(hours=2), 3.0)  # latest for A
    await _insert_score(session, b, base, 9.0)
    await _insert_score(session, b, base + timedelta(hours=1), 9.5)  # latest for B
    await session.commit()

    result = await session.execute(
        text(
            "SELECT agent_id, agent_score FROM current_scores "
            "ORDER BY agent_id"
        )
    )
    rows = result.all()
    assert len(rows) == 2
    by_agent = {row[0]: row[1] for row in rows}
    assert by_agent[a] == Decimal("3.0000")
    assert by_agent[b] == Decimal("9.5000")


async def test_current_scores_one_row_per_agent_under_load(
    session: AsyncSession,
) -> None:
    """Insert N agents with M scores each; current_scores must return exactly N rows."""
    n_agents = 50
    scores_per_agent = 20

    agent_ids = [
        await _insert_agent(session, f"loadtest-{i:03d}") for i in range(n_agents)
    ]
    base = datetime.now(timezone.utc) - timedelta(days=1)

    for i, aid in enumerate(agent_ids):
        for k in range(scores_per_agent):
            # Varying timestamps so the "latest" is unambiguous and varies.
            ts = base + timedelta(minutes=k * 7 + i)
            await _insert_score(session, aid, ts, float(k))
    await session.commit()

    count = (await session.execute(text("SELECT count(*) FROM current_scores"))).scalar_one()
    assert count == n_agents

    total = (await session.execute(text("SELECT count(*) FROM scores"))).scalar_one()
    assert total == n_agents * scores_per_agent

    # Every returned row is the max(computed_at) for its agent.
    result = await session.execute(
        text(
            """
            WITH expected AS (
                SELECT agent_id, max(computed_at) AS latest FROM scores GROUP BY agent_id
            )
            SELECT count(*) FROM current_scores cs
            JOIN expected e
              ON e.agent_id = cs.agent_id AND e.latest = cs.computed_at
            """
        )
    )
    assert result.scalar_one() == n_agents


# ---------------------------------------------------------------- pgvector


async def test_pgvector_column_accepts_vector(session: AsyncSession) -> None:
    agent_id = await _insert_agent(session, "vec-test")
    embedding = [0.1] * 1536
    await session.execute(
        text("UPDATE agents SET embedding = :v WHERE id = :id"),
        {"v": str(embedding), "id": agent_id},
    )
    await session.commit()
    result = await session.execute(
        text("SELECT embedding IS NOT NULL FROM agents WHERE id = :id"),
        {"id": agent_id},
    )
    assert result.scalar_one() is True
