"""On-connect snapshot frames.

Each WS / SSE endpoint sends one ``snapshot`` frame as the very first
message so the client doesn't have to round-trip to the REST API to
populate state. Snapshots are intentionally compact:

- ticker:    last 50 events
- agent:     header + current_scores envelope
- index:     definition + members + composite + last_rebalance_at
- watchlist: per-slug header + current_scores envelopes
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _to_isoz(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


async def ticker_snapshot(session: AsyncSession, *, limit: int = 50) -> dict[str, Any]:
    rows = await session.execute(
        text(
            """
            SELECT id, kind, agent_id, payload, created_at
            FROM events
            ORDER BY created_at DESC LIMIT :n
            """
        ),
        {"n": limit},
    )
    events = []
    for r in rows:
        events.append(
            {
                "id": str(r.id),
                "kind": r.kind,
                "agent_id": str(r.agent_id) if r.agent_id else None,
                "payload": r.payload,
                "created_at": _to_isoz(r.created_at),
            }
        )
    return {"type": "snapshot", "scope": "ticker", "events": events}


async def agent_snapshot(session: AsyncSession, slug: str) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT a.id, a.slug, a.name, a.description, a.discovered_at,
                       cs.agent_score, cs.adoption, cs.quality, cs.momentum,
                       cs.community, cs.manipulation_resistance, cs.computed_at
                FROM agents a
                LEFT JOIN current_scores cs ON cs.agent_id = a.id
                WHERE a.slug = :slug
                """
            ),
            {"slug": slug},
        )
    ).first()
    if row is None:
        return None
    return {
        "type": "snapshot",
        "scope": "agent",
        "agent": {
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name,
            "description": row.description,
            "discovered_at": _to_isoz(row.discovered_at),
        },
        "score": _envelope(row),
    }


async def index_snapshot(session: AsyncSession, slug: str) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT i.id, i.slug, i.name, i.methodology_md,
                       i.rebalance_frequency,
                       (SELECT count(*) FROM index_members
                        WHERE index_id = i.id AND removed_at IS NULL) AS members,
                       (SELECT composite_value FROM index_snapshots s
                        WHERE s.index_id = i.id ORDER BY s.captured_at DESC LIMIT 1)
                            AS composite_value,
                       (SELECT max(run_at) FROM rebalances WHERE index_id = i.id)
                            AS last_rebalance_at
                FROM indexes i WHERE i.slug = :slug
                """
            ),
            {"slug": slug},
        )
    ).first()
    if row is None:
        return None

    members_rows = await session.execute(
        text(
            """
            SELECT a.slug, a.name, im.weight, cs.agent_score
            FROM index_members im
            JOIN agents a ON a.id = im.agent_id
            LEFT JOIN current_scores cs ON cs.agent_id = a.id
            WHERE im.index_id = :iid AND im.removed_at IS NULL
            ORDER BY cs.agent_score DESC NULLS LAST
            """
        ),
        {"iid": row.id},
    )
    members = [
        {
            "slug": m.slug,
            "name": m.name,
            "weight": float(m.weight),
            "agent_score": float(m.agent_score) if m.agent_score is not None else None,
        }
        for m in members_rows
    ]
    return {
        "type": "snapshot",
        "scope": "index",
        "index": {
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name,
            "methodology_md": row.methodology_md,
            "rebalance_frequency": row.rebalance_frequency,
            "members_count": int(row.members or 0),
            "composite_value": (
                float(row.composite_value) if row.composite_value is not None else None
            ),
            "last_rebalance_at": _to_isoz(row.last_rebalance_at),
        },
        "members": members,
    }


async def watchlist_snapshot(
    session: AsyncSession, slugs: list[str]
) -> dict[str, Any]:
    if not slugs:
        return {"type": "snapshot", "scope": "watchlist", "agents": []}
    rows = await session.execute(
        text(
            """
            SELECT a.slug, a.name, a.description, a.discovered_at,
                   cs.agent_score, cs.adoption, cs.quality, cs.momentum,
                   cs.community, cs.manipulation_resistance, cs.computed_at
            FROM agents a
            LEFT JOIN current_scores cs ON cs.agent_id = a.id
            WHERE a.slug = ANY(:slugs)
            """
        ),
        {"slugs": list(slugs)},
    )
    agents = []
    for r in rows:
        agents.append(
            {
                "slug": r.slug,
                "name": r.name,
                "description": r.description,
                "discovered_at": _to_isoz(r.discovered_at),
                "score": _envelope(r),
            }
        )
    return {"type": "snapshot", "scope": "watchlist", "agents": agents}


def _envelope(row: Any) -> dict[str, Any]:
    """Strict ScoreEnvelope shape, matching the REST API's contract."""
    return {
        "agent_score": float(row.agent_score) if row.agent_score is not None else None,
        "adoption": float(row.adoption) if row.adoption is not None else None,
        "quality": float(row.quality) if row.quality is not None else None,
        "momentum": float(row.momentum) if row.momentum is not None else None,
        "community": float(row.community) if row.community is not None else None,
        "manipulation_resistance": (
            float(row.manipulation_resistance)
            if row.manipulation_resistance is not None
            else None
        ),
        "computed_at": _to_isoz(row.computed_at),
    }
