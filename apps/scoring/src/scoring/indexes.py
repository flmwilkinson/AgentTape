"""Index definitions, rebalance, and snapshots.

Five indexes at launch:

    TAPE-100   — top 100 admitted agents by AgentScore (the flagship)
    CODE-25    — top 25 with capability tag = code-generation
    WEB-25     — top 25 with capability tag = browsing
    OSS-50     — top 50 with an OSI-approved license
    MCP-25     — top 25 with deployment tag = mcp-server

Eligibility rules live in ``indexes.eligibility_rules`` (jsonb) so they
can be tweaked from the API without a code deploy. ``ensure_indexes``
upserts them on every service start so a fresh DB is usable
immediately.

Rebalance:
    - select agents matching the index's eligibility rules + ordered by
      latest AgentScore from current_scores
    - keep top N
    - diff against the active membership (added / removed / weight_changes)
    - INSERT into rebalances + INSERT/UPDATE index_members
    - snapshot the index value into index_snapshots
    - emit index_rebalanced event
    - generate a Claude narrative (best-effort)

Snapshots without rebalance: hourly cron writes the live composite value
to index_snapshots so the dashboard ticker has a continuous time-series.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scoring.config import Settings, get_settings
from scoring.narrative import generate_rebalance_narrative

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- catalog


@dataclass(frozen=True)
class IndexDef:
    slug: str
    name: str
    methodology_md: str
    rebalance_frequency: str  # "weekly" / "monthly"
    eligibility_rules: dict[str, Any]


OSI_APPROVED_LICENSES = ["mit", "apache-2.0", "bsd", "mpl", "agpl", "gpl"]


CATALOG: list[IndexDef] = [
    # Flagship — top 100 application agents.
    IndexDef(
        slug="tape-100",
        name="TAPE-100",
        methodology_md=(
            "The 100 application agents with the highest AgentScore.\n"
            "Foundation models live in FM-50; this index is application-only.\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={"top_n": 100, "entity_kind": "application"},
    ),
    # Foundation-model basket — same scoring formula but only models.
    IndexDef(
        slug="fm-50",
        name="FM-50",
        methodology_md=(
            "Top 50 foundation models by AgentScore. Sourced from the\n"
            "openrouter.ai catalogue and scored against the same four\n"
            "pillars as application agents — Quality dominates here\n"
            "because benchmarks ARE the product for foundation models.\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={"top_n": 50, "entity_kind": "foundation_model"},
    ),
    # Sector indexes — application agents grouped by capability /
    # deployment / license. All scope themselves to entity_kind=application
    # so foundation models don't pollute the sector lists.
    IndexDef(
        slug="code-25",
        name="CODE-25",
        methodology_md=(
            "Top 25 application agents with a `code-generation` capability tag.\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={
            "top_n": 25,
            "entity_kind": "application",
            "tag": {"kind": "capability", "value": "code-generation"},
        },
    ),
    IndexDef(
        slug="web-25",
        name="WEB-25",
        methodology_md=(
            "Top 25 application agents with a `browsing` capability tag.\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={
            "top_n": 25,
            "entity_kind": "application",
            "tag": {"kind": "capability", "value": "browsing"},
        },
    ),
    IndexDef(
        slug="oss-50",
        name="OSS-50",
        methodology_md=(
            "Top 50 application agents whose license tag is OSI-approved\n"
            "(MIT, Apache-2.0, BSD, MPL, AGPL, GPL).\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={
            "top_n": 50,
            "entity_kind": "application",
            "license_in": OSI_APPROVED_LICENSES,
        },
    ),
    IndexDef(
        slug="mcp-25",
        name="MCP-25",
        methodology_md=(
            "Top 25 application agents with deployment tag `mcp-server`.\n"
            "Equal-weighted v1. Rebalances Mondays 03:00 UTC."
        ),
        rebalance_frequency="weekly",
        eligibility_rules={
            "top_n": 25,
            "entity_kind": "application",
            "tag": {"kind": "deployment", "value": "mcp-server"},
        },
    ),
]


CATALOG_BY_SLUG: dict[str, IndexDef] = {d.slug: d for d in CATALOG}


# ---------------------------------------------------------------- bootstrap


async def ensure_indexes(session: AsyncSession) -> None:
    """Upsert the five launch indexes — idempotent on conflict on slug."""
    for d in CATALOG:
        await session.execute(
            text(
                """
                INSERT INTO indexes (
                    id, slug, name, methodology_md,
                    rebalance_frequency, eligibility_rules
                ) VALUES (
                    gen_random_uuid(), :slug, :name, :method,
                    :freq, CAST(:rules AS jsonb)
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    methodology_md = EXCLUDED.methodology_md,
                    rebalance_frequency = EXCLUDED.rebalance_frequency,
                    eligibility_rules = EXCLUDED.eligibility_rules
                """
            ),
            {
                "slug": d.slug,
                "name": d.name,
                "method": d.methodology_md,
                "freq": d.rebalance_frequency,
                "rules": json.dumps(d.eligibility_rules),
            },
        )
    await session.commit()


async def _index_id(session: AsyncSession, slug: str) -> UUID:
    r = await session.execute(text("SELECT id FROM indexes WHERE slug = :s"), {"s": slug})
    return r.scalar_one()


# ---------------------------------------------------------------- selection


async def _candidates(
    session: AsyncSession, definition: IndexDef
) -> list[tuple[UUID, float]]:
    """Return [(agent_id, current_score), ...] eligible for this index, ordered."""
    rules = definition.eligibility_rules
    where = ["a.eligibility_status = 'admitted'"]
    params: dict[str, Any] = {}

    # entity_kind filter — application vs foundation_model vs framework /
    # mcp_server. Defaults to application so legacy index defs without
    # this rule keep their old behavior.
    entity_kind = rules.get("entity_kind", "application")
    where.append("a.entity_kind = :entity_kind")
    params["entity_kind"] = entity_kind

    sql_join = ""
    tag_rule = rules.get("tag")
    if tag_rule:
        sql_join += (
            " JOIN agent_tags at ON at.agent_id = a.id"
            " JOIN tags t ON t.id = at.tag_id"
            " AND t.kind = CAST(:tag_kind AS tag_kind) AND t.value = :tag_value"
        )
        params["tag_kind"] = tag_rule["kind"]
        params["tag_value"] = tag_rule["value"]

    license_rule = rules.get("license_in")
    if license_rule:
        sql_join += (
            " JOIN agent_tags at_lic ON at_lic.agent_id = a.id"
            " JOIN tags t_lic ON t_lic.id = at_lic.tag_id"
            " AND t_lic.kind = 'license' AND t_lic.value = ANY(:lic)"
        )
        # asyncpg wants a Python list for text[] params; the {...} string
        # only works through the psycopg2 dialect.
        params["lic"] = list(license_rule)

    sql = (
        "SELECT a.id, cs.agent_score FROM agents a "
        "JOIN current_scores cs ON cs.agent_id = a.id "
        + sql_join
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY cs.agent_score DESC LIMIT :n"
    )
    params["n"] = rules.get("top_n", 100)
    rows = (await session.execute(text(sql), params)).all()
    return [(r[0], float(r[1])) for r in rows]


# ---------------------------------------------------------------- diff


@dataclass
class RebalanceDiff:
    additions: list[dict[str, Any]]
    removals: list[dict[str, Any]]
    weight_changes: list[dict[str, Any]]


async def _active_members(
    session: AsyncSession, index_id: UUID
) -> dict[UUID, float]:
    rows = await session.execute(
        text(
            """
            SELECT agent_id, weight FROM index_members
            WHERE index_id = :iid AND removed_at IS NULL
            """
        ),
        {"iid": index_id},
    )
    return {r[0]: float(r[1]) for r in rows}


def _diff(
    current: dict[UUID, float], proposed: dict[UUID, float]
) -> RebalanceDiff:
    added = [
        {"agent_id": str(aid), "weight": w}
        for aid, w in proposed.items()
        if aid not in current
    ]
    removed = [
        {"agent_id": str(aid), "old_weight": w}
        for aid, w in current.items()
        if aid not in proposed
    ]
    changed = [
        {"agent_id": str(aid), "old_weight": current[aid], "new_weight": w}
        for aid, w in proposed.items()
        if aid in current and abs(current[aid] - w) > 1e-9
    ]
    return RebalanceDiff(additions=added, removals=removed, weight_changes=changed)


# ---------------------------------------------------------------- rebalance


async def rebalance_index(
    session: AsyncSession,
    redis_client: Any,
    slug: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    definition = CATALOG_BY_SLUG[slug]
    index_id = await _index_id(session, slug)

    candidates = await _candidates(session, definition)
    n = len(candidates)
    if n == 0:
        log.warning("rebalance %s: no eligible agents", slug)
        proposed: dict[UUID, float] = {}
    else:
        weight = 1.0 / n  # equal-weight v1
        proposed = {aid: weight for aid, _ in candidates}

    current = await _active_members(session, index_id)
    diff = _diff(current, proposed)

    # Apply: mark every active member as removed at rebalance time, then
    # insert one fresh row per proposed agent. This gives each rebalance
    # a clean snapshot — the old "leave the existing row alone if the
    # agent is still in the proposed set" behavior could double-count
    # if the same agent appeared in successive rebalances at different
    # added_at timestamps (the PK includes added_at). The trade-off is
    # that "added_at" no longer means "first added"; for that history
    # the rebalances table is the source of truth.
    now = datetime.now(UTC)
    await session.execute(
        text(
            """
            UPDATE index_members
            SET removed_at = :now
            WHERE index_id = :iid AND removed_at IS NULL
            """
        ),
        {"now": now, "iid": index_id},
    )
    for aid, w in proposed.items():
        await session.execute(
            text(
                """
                INSERT INTO index_members (index_id, agent_id, added_at, weight, removed_at)
                VALUES (:iid, :aid, :now, :w, NULL)
                ON CONFLICT (index_id, agent_id, added_at) DO UPDATE SET weight = EXCLUDED.weight
                """
            ),
            {"iid": index_id, "aid": aid, "now": now, "w": w},
        )

    composite = _composite_value(candidates)
    snapshot = {
        "members": [
            {"agent_id": str(aid), "score": s, "weight": proposed[aid]}
            for aid, s in candidates
            if aid in proposed
        ]
    }
    await session.execute(
        text(
            """
            INSERT INTO index_snapshots (id, index_id, captured_at, composite_value, constituents)
            VALUES (gen_random_uuid(), :iid, :now, :v, CAST(:c AS jsonb))
            """
        ),
        {"iid": index_id, "now": now, "v": composite, "c": json.dumps(snapshot)},
    )

    narrative = await generate_rebalance_narrative(
        settings, definition, diff, candidates
    )

    await session.execute(
        text(
            """
            INSERT INTO rebalances (
                id, index_id, run_at, additions, removals, weight_changes, narrative_md
            ) VALUES (
                gen_random_uuid(), :iid, :now,
                CAST(:add AS jsonb), CAST(:rem AS jsonb),
                CAST(:wch AS jsonb), :narr
            )
            """
        ),
        {
            "iid": index_id,
            "now": now,
            "add": json.dumps(diff.additions),
            "rem": json.dumps(diff.removals),
            "wch": json.dumps(diff.weight_changes),
            "narr": narrative,
        },
    )

    payload = {
        "kind": "index_rebalanced",
        "index_slug": slug,
        "members": len(proposed),
        "additions": len(diff.additions),
        "removals": len(diff.removals),
        "composite_value": composite,
    }
    await session.execute(
        text(
            """
            INSERT INTO events (id, kind, payload)
            VALUES (gen_random_uuid(), CAST('index_rebalanced' AS event_kind), CAST(:p AS jsonb))
            """
        ),
        {"p": json.dumps(payload)},
    )
    body = json.dumps(payload)
    try:
        await redis_client.publish("events.global", body)
        await redis_client.publish(f"events.index.{slug}", body)
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (rebalance) failed: %s", e)

    await session.commit()
    log.info(
        "rebalance %s: %d members, +%d -%d ~%d",
        slug,
        len(proposed),
        len(diff.additions),
        len(diff.removals),
        len(diff.weight_changes),
    )
    return {
        "index": slug,
        "members": len(proposed),
        "additions": len(diff.additions),
        "removals": len(diff.removals),
        "weight_changes": len(diff.weight_changes),
        "composite_value": composite,
    }


def _composite_value(candidates: list[tuple[UUID, float]]) -> float:
    """Equal-weighted average of constituent scores. Index level on the 0-100 scale."""
    if not candidates:
        return 0.0
    return float(sum(s for _, s in candidates) / len(candidates))


# ---------------------------------------------------------------- snapshot


async def snapshot_all_indexes(session: AsyncSession) -> dict[str, Any]:
    """Hourly job — write the live composite value of every index."""
    out: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    for d in CATALOG:
        index_id = await _index_id(session, d.slug)
        rows = await session.execute(
            text(
                """
                SELECT cs.agent_score
                FROM index_members im
                JOIN current_scores cs ON cs.agent_id = im.agent_id
                WHERE im.index_id = :iid AND im.removed_at IS NULL
                """
            ),
            {"iid": index_id},
        )
        scores = [float(r[0]) for r in rows]
        composite = float(sum(scores) / len(scores)) if scores else 0.0
        await session.execute(
            text(
                """
                INSERT INTO index_snapshots (id, index_id, captured_at, composite_value, constituents)
                VALUES (gen_random_uuid(), :iid, :now, :v, CAST(:c AS jsonb))
                """
            ),
            {
                "iid": index_id,
                "now": now,
                "v": composite,
                "c": json.dumps({"members": len(scores)}),
            },
        )
        out.append({"index": d.slug, "members": len(scores), "composite_value": composite})
    await session.commit()
    return {"snapshots": out}


async def rebalance_all(
    session: AsyncSession, redis_client: Any
) -> dict[str, Any]:
    out = []
    for d in CATALOG:
        out.append(await rebalance_index(session, redis_client, d.slug))
    return {"rebalances": out}
