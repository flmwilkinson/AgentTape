"""/sectors — sector-level rollup for capability / deployment / maturity.

For each tag value within a kind, returns the count of admitted agents,
the average AgentScore now, the average 7 days ago, and a verdict
classification (booming / growing / steady / cooling / declining) so a
reader can answer "which sector is heating up" at a glance.

This drives /sectors on the web app — an index of indexes, basically.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api.deps import get_session

router = APIRouter(prefix="/sectors", tags=["sectors"])

# Verdict thresholds — chosen by feel against a 0–100 score range. The
# "booming" cut is the same magnitude that draws attention on the
# /trending page.
BOOMING = 2.0
GROWING = 0.5
COOLING = -0.5
DECLINING = -2.0


def _verdict(delta: float | None) -> str:
    if delta is None:
        return "no_history"
    if delta >= BOOMING:
        return "booming"
    if delta >= GROWING:
        return "growing"
    if delta > COOLING:
        return "steady"
    if delta > DECLINING:
        return "cooling"
    return "declining"


@router.get("/{kind}/{value}/history")
async def get_sector_history(
    kind: str,
    value: str,
    window: str = Query("30d", pattern="^(1d|7d|30d|90d|all)$"),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[dict[str, Any]]:
    """Time-bucketed average AgentScore for the cohort tagged (kind, value).

    Bucket size scales with the window so the chart always lands at
    a few hundred points: 5-min for 1d, hourly for 7d, daily beyond.
    Aligned with the 5-min scoring heartbeat.
    """
    if kind not in {"capability", "deployment", "maturity", "domain", "license"}:
        return []
    delta_map = {
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    since = (
        datetime.now(UTC) - delta_map[window]
        if window != "all"
        else datetime(2024, 1, 1, tzinfo=UTC)
    )

    # Bucket SQL — 5-min uses arithmetic on epoch seconds; the others
    # use Postgres date_trunc. Picked so each window lands at roughly
    # the same number of points (~144–288).
    if window == "1d":
        bucket_expr = (
            "to_timestamp(floor(extract(epoch from s.computed_at) / 300) * 300)"
        )
    elif window == "7d":
        bucket_expr = "date_trunc('hour', s.computed_at)"
    else:
        bucket_expr = "date_trunc('day', s.computed_at)"

    rows = await session.execute(
        text(
            f"""
            WITH cohort AS (
                SELECT a.id
                FROM tags t
                JOIN agent_tags at ON at.tag_id = t.id
                JOIN agents a ON a.id = at.agent_id
                WHERE t.kind = CAST(:kind AS tag_kind)
                  AND t.value = :value
                  AND a.eligibility_status = 'admitted'
            )
            SELECT {bucket_expr} AS bucket,
                   AVG(s.agent_score)::float AS avg_score,
                   COUNT(DISTINCT s.agent_id) AS agents
            FROM scores s
            WHERE s.agent_id IN (SELECT id FROM cohort)
              AND s.computed_at >= :since
            GROUP BY 1
            ORDER BY 1 ASC
            """
        ),
        {"kind": kind, "value": value, "since": since},
    )
    return [
        {
            "captured_at": r.bucket,
            "avg_score": float(r.avg_score) if r.avg_score is not None else None,
            "agents": int(r.agents),
        }
        for r in rows
    ]


@router.get("")
async def get_sectors(
    kind: str = Query("capability", pattern="^(capability|deployment|maturity)$"),
    window: str = Query("7d", pattern="^(1d|7d|30d)$"),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[dict[str, Any]]:
    delta_map = {
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    since = datetime.now(UTC) - delta_map[window]

    # For each tag in the requested kind, average the headline score
    # over its tagged agents (current) and the agent's score
    # at-or-before the window start. Agents with no score history
    # before the window are excluded from the "then" average so the
    # delta isn't skewed by recent admissions.
    rows = await session.execute(
        text(
            """
            WITH tag_agents AS (
                SELECT t.value AS tag_value, t.display_name, a.id AS agent_id,
                    cs.agent_score AS now_score
                FROM tags t
                JOIN agent_tags at ON at.tag_id = t.id
                JOIN agents a ON a.id = at.agent_id
                LEFT JOIN current_scores cs ON cs.agent_id = a.id
                WHERE t.kind = CAST(:kind AS tag_kind)
                    AND a.eligibility_status = 'admitted'
            ),
            then_scores AS (
                SELECT ta.tag_value, ta.agent_id,
                    (SELECT s.agent_score FROM scores s
                     WHERE s.agent_id = ta.agent_id
                       AND s.computed_at <= :since
                     ORDER BY s.computed_at DESC LIMIT 1) AS then_score
                FROM tag_agents ta
            )
            SELECT ta.tag_value AS value,
                MAX(ta.display_name) AS display_name,
                COUNT(DISTINCT ta.agent_id) AS members,
                AVG(ta.now_score)::float AS avg_now,
                AVG(ts.then_score)::float AS avg_then
            FROM tag_agents ta
            LEFT JOIN then_scores ts ON ts.agent_id = ta.agent_id
            GROUP BY ta.tag_value
            HAVING COUNT(DISTINCT ta.agent_id) >= 1
            ORDER BY AVG(ta.now_score) DESC NULLS LAST
            """
        ),
        {"kind": kind, "since": since},
    )

    out: list[dict[str, Any]] = []
    for r in rows:
        avg_now = float(r.avg_now) if r.avg_now is not None else None
        avg_then = float(r.avg_then) if r.avg_then is not None else None
        delta = (
            avg_now - avg_then
            if avg_now is not None and avg_then is not None
            else None
        )
        out.append(
            {
                "value": r.value,
                "display_name": r.display_name,
                "members": int(r.members),
                "avg_now": avg_now,
                "avg_then": avg_then,
                "delta": delta,
                "verdict": _verdict(delta),
            }
        )
    return out


@router.get("/top")
async def get_sectors_top(
    kind: str = Query("capability", pattern="^(capability|deployment|maturity)$"),
    top: int = Query(3, ge=1, le=10),
    entity_kind: str | None = Query(
        None, pattern="^(application|foundation_model)$"
    ),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[dict[str, Any]]:
    """Top-N agents per tag value, in one query.

    Why this endpoint exists: the Floor's "find the right agent" rail
    used to fan out N parallel ``/agents?tag_kind=…`` calls (one per
    capability), each running the heavy listing query (joins to
    current_scores, two LATERALs, the global rank subquery). With ten
    capabilities under a 2-second client-side timeout, enough of those
    calls timed out that the rail came back empty for production
    users — the same data /sectors and /search were happily serving
    via single queries.

    A single ROW_NUMBER OVER (PARTITION BY tag_value ORDER BY score)
    does the same job in one round-trip and produces the exact shape
    the rail needs: per tag value, the top-N agents with their slug,
    name, score, and external links.

    Each agent row carries only what the rail renders. If a richer
    payload is needed downstream the caller can /agents/<slug> for
    the detail.
    """
    extra_where = ""
    params: dict[str, Any] = {"kind": kind, "top": top}
    if entity_kind:
        extra_where = " AND a.entity_kind = :entity_kind"
        params["entity_kind"] = entity_kind
    rows = await session.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    t.value AS tag_value,
                    t.display_name,
                    a.id, a.slug, a.name, a.entity_kind,
                    a.homepage_url, a.github_repo,
                    cs.agent_score AS agent_score,
                    cs.adoption, cs.quality, cs.momentum, cs.community,
                    s24.score_24h_ago,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.value
                        ORDER BY cs.agent_score DESC NULLS LAST, a.slug ASC
                    ) AS rn
                FROM tags t
                JOIN agent_tags at_ ON at_.tag_id = t.id
                JOIN agents a ON a.id = at_.agent_id
                LEFT JOIN current_scores cs ON cs.agent_id = a.id
                LEFT JOIN LATERAL (
                    SELECT s.agent_score AS score_24h_ago FROM scores s
                    WHERE s.agent_id = a.id
                      AND s.computed_at <= now() - interval '24 hours'
                    ORDER BY s.computed_at DESC LIMIT 1
                ) s24 ON true
                WHERE t.kind = CAST(:kind AS tag_kind)
                  AND a.eligibility_status = 'admitted'{extra_where}
            )
            SELECT * FROM ranked
            WHERE rn <= :top
            ORDER BY tag_value ASC, rn ASC
            """
        ),
        params,
    )

    groups: dict[str, dict[str, Any]] = {}
    for r in rows:
        bucket = groups.setdefault(
            r.tag_value,
            {
                "value": r.tag_value,
                "display_name": r.display_name,
                "agents": [],
            },
        )
        score_now = float(r.agent_score) if r.agent_score is not None else None
        score_24h = float(r.score_24h_ago) if r.score_24h_ago is not None else None
        delta_24h = (
            score_now - score_24h
            if score_now is not None and score_24h is not None
            else None
        )
        bucket["agents"].append(
            {
                "id": str(r.id),
                "slug": r.slug,
                "name": r.name,
                "entity_kind": r.entity_kind,
                "homepage_url": r.homepage_url,
                "github_repo": r.github_repo,
                "score": {
                    "agent_score": score_now,
                    "adoption": float(r.adoption) if r.adoption is not None else None,
                    "quality": float(r.quality) if r.quality is not None else None,
                    "momentum": float(r.momentum) if r.momentum is not None else None,
                    "community": (
                        float(r.community) if r.community is not None else None
                    ),
                    "efficiency": (
                        float(r.efficiency) if r.efficiency is not None else None
                    ),
                    "score_24h_ago": score_24h,
                    "delta_24h": delta_24h,
                },
            }
        )
    return list(groups.values())
