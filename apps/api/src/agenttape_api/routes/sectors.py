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
