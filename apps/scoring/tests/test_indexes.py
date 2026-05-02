"""Index + rebalance tests."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from scoring.compute import recompute_agents
from scoring.indexes import (
    CATALOG_BY_SLUG,
    ensure_indexes,
    rebalance_index,
    snapshot_all_indexes,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("_reset_data")]


async def _seed_with_tags(session, n: int = 30) -> list[uuid.UUID]:
    """Synthetic dataset where:
    - agents 0..9   have capability=code-generation
    - agents 10..19 have capability=browsing
    - agents 0..14  have license=mit
    - agents 20..29 have deployment=mcp-server
    Stars increase with index so headline scores increase too.
    """
    from tests.conftest import add_signal, make_agent  # type: ignore

    aids: list[uuid.UUID] = []
    for i in range(n):
        capability = None
        deployment = None
        license_value = None
        if i < 10:
            capability = "code-generation"
        elif i < 20:
            capability = "browsing"
        if i < 15:
            license_value = "mit"
        if i >= 20:
            deployment = "mcp-server"

        aid = await make_agent(
            session,
            slug=f"agent-{i:03d}",
            capability_value=capability,
            license_value=license_value,
            deployment_value=deployment,
        )
        aids.append(aid)
        await add_signal(session, aid, "github_stars", 100.0 * (i + 1))
        await add_signal(session, aid, "hf_downloads_30d", 50.0 * (i + 1))
        await add_signal(session, aid, "github_contributors", float(i + 1))
        await add_signal(session, aid, "hn_points_7d", float(i + 1))
    await session.commit()
    return aids


async def _seed_indexes_and_score(session, redis_client, settings, n: int = 30):
    aids = await _seed_with_tags(session, n)
    await ensure_indexes(session)
    await recompute_agents(session, aids, redis_client, settings)
    return aids


# ------------------------------------------------------- bootstrap


async def test_ensure_indexes_creates_five_definitions(
    session, settings_with_db
):
    await ensure_indexes(session)
    rows = (
        await session.execute(text("SELECT slug FROM indexes ORDER BY slug"))
    ).all()
    slugs = [r[0] for r in rows]
    assert slugs == sorted(CATALOG_BY_SLUG)


async def test_ensure_indexes_is_idempotent(session, settings_with_db):
    await ensure_indexes(session)
    await ensure_indexes(session)
    cnt = (
        await session.execute(text("SELECT count(*) FROM indexes"))
    ).scalar_one()
    assert cnt == len(CATALOG_BY_SLUG)


# ------------------------------------------------------- selection


async def test_code25_only_selects_code_capability(
    session, settings_with_db, redis_client
):
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    result = await rebalance_index(session, redis_client, "code-25")
    # Only 10 agents had capability=code-generation.
    assert result["members"] == 10

    rows = (
        await session.execute(
            text(
                """
                SELECT a.slug FROM index_members im
                JOIN agents a ON a.id = im.agent_id
                JOIN indexes i ON i.id = im.index_id
                WHERE i.slug = 'code-25' AND im.removed_at IS NULL
                """
            )
        )
    ).all()
    slugs = {r[0] for r in rows}
    # Code-tagged agents are 0..9.
    assert slugs == {f"agent-{i:03d}" for i in range(10)}


async def test_oss50_only_selects_osi_licenses(
    session, settings_with_db, redis_client
):
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    result = await rebalance_index(session, redis_client, "oss-50")
    # Only 15 agents had license=mit.
    assert result["members"] == 15


async def test_mcp25_only_selects_mcp_servers(
    session, settings_with_db, redis_client
):
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    result = await rebalance_index(session, redis_client, "mcp-25")
    assert result["members"] == 10  # agents 20..29 had deployment=mcp-server


# ------------------------------------------------------- diff


async def test_rebalance_diff_when_membership_changes(
    session, settings_with_db, redis_client
):
    """Initial rebalance with all 5 code-tagged agents -> add another 5 -> rebalance again.

    The second rebalance's ``additions`` must list exactly the new 5.
    """
    from tests.conftest import add_signal, make_agent  # type: ignore

    # First batch: 5 code agents.
    initial: list[uuid.UUID] = []
    for i in range(5):
        aid = await make_agent(
            session,
            slug=f"code-batch1-{i}",
            capability_value="code-generation",
        )
        initial.append(aid)
        await add_signal(session, aid, "github_stars", 100.0 * (i + 1))
    await session.commit()

    await ensure_indexes(session)
    await recompute_agents(session, initial, redis_client, settings_with_db)
    first = await rebalance_index(session, redis_client, "code-25")
    assert first["members"] == 5
    assert first["additions"] == 5

    # Second batch: another 5 code agents, also with stars.
    new_aids: list[uuid.UUID] = []
    for i in range(5):
        aid = await make_agent(
            session,
            slug=f"code-batch2-{i}",
            capability_value="code-generation",
        )
        new_aids.append(aid)
        await add_signal(session, aid, "github_stars", 200.0 * (i + 1))
    await session.commit()
    await recompute_agents(session, initial + new_aids, redis_client, settings_with_db)

    second = await rebalance_index(session, redis_client, "code-25")
    assert second["members"] == 10
    assert second["additions"] == 5
    assert second["removals"] == 0


async def test_snapshots_table_has_one_row_per_index(
    session, settings_with_db, redis_client
):
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    # rebalance_all isn't called here — exercise the lone snapshot path.
    out = await snapshot_all_indexes(session)
    assert len(out["snapshots"]) == len(CATALOG_BY_SLUG)
    cnt = (
        await session.execute(text("SELECT count(*) FROM index_snapshots"))
    ).scalar_one()
    assert cnt == len(CATALOG_BY_SLUG)


async def test_rebalance_writes_event_and_publishes(
    session, settings_with_db, redis_client
):
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    await rebalance_index(session, redis_client, "tape-100")

    events = (
        await session.execute(
            text(
                "SELECT count(*) FROM events "
                "WHERE kind = CAST('index_rebalanced' AS event_kind)"
            )
        )
    ).scalar_one()
    assert events == 1
    # Redis got the publish on tape:rebalances.
    channels = [c for c, _ in redis_client.published]
    assert "tape:rebalances" in channels


async def test_narrative_falls_back_without_anthropic_key(
    session, settings_with_db, redis_client
):
    """No ANTHROPIC_API_KEY: narrative_md is the deterministic fallback (not empty)."""
    await _seed_indexes_and_score(session, redis_client, settings_with_db)
    await rebalance_index(session, redis_client, "tape-100")

    narr = (
        await session.execute(
            text(
                "SELECT narrative_md FROM rebalances ORDER BY run_at DESC LIMIT 1"
            )
        )
    ).scalar_one()
    assert narr
    assert "TAPE-100" in narr or "rebalance" in narr.lower()
