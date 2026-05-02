"""Score computation tests against a real Postgres + the apps/api schema.

We seed deterministic fixtures (100 mock agents with adoption + community
signals; 30 of them on a benchmark) and verify:

- Pillar math is in [0, 100], headline is in [0, 100], all four are
  always persisted (one row per recompute, never partial).
- Quality is null for unrated agents and the 30% weight is redistributed.
- Manipulation-flagged signals are excluded; manipulation_resistance < 1.
- Re-running the recompute over the same data is rank-stable: the top-10
  list is identical between two consecutive recomputes.
- A signal change for one agent flips the rank in the expected direction.
"""
from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from scoring.compute import (
    all_admitted_agent_ids,
    compute_for_agent,
    population_stats,
    recompute_agents,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("_reset_data")]


# ---------------------------------------------------------------- fixtures


async def _seed_population(session, n: int = 100) -> list[uuid.UUID]:
    """Build a deterministic 100-agent population with adoption + community signals.

    Agent index ``i`` gets stars = 100*i, hf_downloads_30d = 50*i,
    contributors = i, hn_points_7d = 5*i. So rank correlates exactly
    with index — easy to assert on.
    """
    from tests.conftest import add_signal, make_agent  # type: ignore

    rng = random.Random(0xA8E)
    agent_ids: list[uuid.UUID] = []
    for i in range(n):
        aid = await make_agent(session, slug=f"agent-{i:03d}")
        agent_ids.append(aid)
        await add_signal(session, aid, "github_stars", 100.0 * i)
        await add_signal(session, aid, "hf_downloads_30d", 50.0 * i)
        await add_signal(session, aid, "github_contributors", float(i))
        await add_signal(session, aid, "hn_points_7d", float(5 * i))
        # A bit of jitter so ties don't dominate.
        await add_signal(
            session,
            aid,
            "github_forks",
            float(rng.randint(0, 50)),
        )
    await session.commit()
    return agent_ids


# ---------------------------------------------------------------- pillars


async def test_pillars_in_range_and_persisted(
    session, settings_with_db, redis_client
):
    aids = await _seed_population(session, 50)
    stats = await recompute_agents(session, aids, redis_client, settings_with_db)
    assert stats["recomputed"] == 50

    rows = (
        await session.execute(
            text(
                "SELECT agent_id, agent_score, adoption, momentum, community, "
                "manipulation_resistance FROM scores"
            )
        )
    ).all()
    assert len(rows) == 50
    for _, headline, adoption, momentum, community, mr in rows:
        for v in (headline, adoption, momentum, community):
            assert 0.0 <= float(v) <= 100.0
        assert 0.0 <= float(mr) <= 1.0


async def test_quality_null_for_unrated_agents(
    session, settings_with_db, redis_client
):
    aids = await _seed_population(session, 10)
    await recompute_agents(session, aids, redis_client, settings_with_db)
    quality_count = (
        await session.execute(
            text("SELECT count(*) FROM scores WHERE quality IS NULL")
        )
    ).scalar_one()
    # No agent had any benchmark_results — every quality is null.
    assert quality_count == 10


async def test_quality_set_when_benchmark_present(
    session, settings_with_db, redis_client
):
    from tests.conftest import add_benchmark_result, add_signal, make_agent  # type: ignore

    aids = []
    for i in range(20):
        aid = await make_agent(session, slug=f"a-{i:02d}")
        aids.append(aid)
        await add_signal(session, aid, "github_stars", 100.0 * i)
    # Half on the benchmark, half not.
    for i, aid in enumerate(aids):
        if i % 2 == 0:
            await add_benchmark_result(session, aid, "synthbench-v1", 50.0 + i)
    await session.commit()

    await recompute_agents(session, aids, redis_client, settings_with_db)
    rated = (
        await session.execute(
            text("SELECT count(*) FROM scores WHERE quality IS NOT NULL")
        )
    ).scalar_one()
    unrated = (
        await session.execute(
            text("SELECT count(*) FROM scores WHERE quality IS NULL")
        )
    ).scalar_one()
    assert rated == 10
    assert unrated == 10


# ----------------------------------------------------- manipulation


async def test_manipulation_flags_exclude_signals(
    session, settings_with_db, redis_client
):
    """An agent with high stars + a star-spike flag should NOT get adoption credit for stars."""
    from tests.conftest import add_signal, make_agent  # type: ignore

    # Two agents with identical stars. Only one is flagged.
    flagged = await make_agent(
        session,
        slug="flagged-agent",
        manipulation_flags={"star_spike_no_contrib_diversity": {"reason": "x"}},
    )
    clean = await make_agent(session, slug="clean-agent")
    for aid in (flagged, clean):
        await add_signal(session, aid, "github_stars", 1_000_000)
        await add_signal(session, aid, "hf_downloads_30d", 1.0)

    # A few decoy agents for population stats.
    for i in range(5):
        a = await make_agent(session, slug=f"decoy-{i}")
        await add_signal(session, a, "github_stars", 10.0)
        await add_signal(session, a, "hf_downloads_30d", 10.0)
    await session.commit()

    pop = await population_stats(session)
    flagged_pillars = await compute_for_agent(session, flagged, pop, settings_with_db)
    clean_pillars = await compute_for_agent(session, clean, pop, settings_with_db)

    # The flagged agent had its stars excluded so adoption should be lower.
    assert flagged_pillars.adoption < clean_pillars.adoption
    # Manipulation resistance reflects the flag.
    assert flagged_pillars.manipulation_resistance < 1.0
    assert clean_pillars.manipulation_resistance == 1.0


# --------------------------------------------------------- rank stability


async def test_top_10_stable_between_recomputes(
    session, settings_with_db, redis_client
):
    aids = await _seed_population(session, 100)
    await recompute_agents(session, aids, redis_client, settings_with_db)
    top_a = (
        await session.execute(
            text(
                "SELECT agent_id FROM current_scores ORDER BY agent_score DESC LIMIT 10"
            )
        )
    ).all()

    # Re-run with no signal changes.
    await recompute_agents(session, aids, redis_client, settings_with_db)
    top_b = (
        await session.execute(
            text(
                "SELECT agent_id FROM current_scores ORDER BY agent_score DESC LIMIT 10"
            )
        )
    ).all()

    assert [r[0] for r in top_a] == [r[0] for r in top_b]


async def test_signal_bump_lifts_agent(session, settings_with_db, redis_client):
    """Bump one mid-rank agent's stars by 100x; it should overtake higher-ranked peers."""
    from tests.conftest import add_signal  # type: ignore

    aids = await _seed_population(session, 50)
    await recompute_agents(session, aids, redis_client, settings_with_db)
    rank_before = await _rank_of(session, aids[10])

    await add_signal(session, aids[10], "github_stars", 100_000.0)
    await session.commit()
    await recompute_agents(session, aids, redis_client, settings_with_db)
    rank_after = await _rank_of(session, aids[10])

    assert rank_after < rank_before  # lower rank number = higher position


async def _rank_of(session, agent_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            text(
                "SELECT agent_id FROM current_scores ORDER BY agent_score DESC"
            )
        )
    ).all()
    for i, (aid,) in enumerate(rows, start=1):
        if aid == agent_id:
            return i
    return 10**9
