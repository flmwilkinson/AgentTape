"""/agents endpoints."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import (
    AgentDetail,
    AgentSummary,
    BenchmarkResultOut,
    Page,
    SignalSeries,
    SimilarAgent,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=Page[AgentSummary])
async def list_agents(
    q: str | None = Query(None, description="Substring match on slug/name/description"),
    tag_kind: str | None = Query(None, description="Filter by tag kind (capability/domain/...)"),
    tag_value: str | None = Query(None, description="Filter by tag value"),
    entity_kind: str | None = Query(
        None, pattern="^(application|foundation_model|framework|mcp_server)$"
    ),
    sort: str = Query("score", pattern="^(score|discovered|name)$"),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> Page[AgentSummary]:
    items, total = await queries.list_agents(
        session,
        q=q,
        tag_kind=tag_kind,
        tag_value=tag_value,
        entity_kind=entity_kind,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return Page[AgentSummary](items=items, total=total, limit=limit, offset=offset)


@router.get("/{slug}", response_model=AgentDetail)
async def get_agent(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> AgentDetail:
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    # Derived badges — computed at request time and dropped onto the
    # detail payload. None when there isn't enough data to decide
    # (agent <60d old, no OpenRouter reading yet, etc.).
    detail["retention"] = await queries.compute_retention_badge(
        session, detail["id"]
    )
    if detail.get("entity_kind") == "foundation_model":
        detail["openrouter_rank"] = await queries.compute_openrouter_rank(
            session, detail["id"]
        )
    return AgentDetail(**detail)


@router.get("/{slug}/signals", response_model=list[SignalSeries])
async def get_agent_signals(
    slug: str,
    sources: list[str] | None = Query(None, description="Filter by signal_source values"),
    window: str = Query("30d", pattern="^(1h|1d|7d|30d|90d|all)$"),
    limit: int = Query(2000, ge=1, le=10_000),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[SignalSeries]:
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    since = _window_to_since(window)
    series = await queries.signals_for_agent(
        session,
        agent_id=detail["id"],
        sources=sources,
        since=since,
        limit=limit,
    )
    return [SignalSeries(**s) for s in series]


@router.get("/{slug}/score-history")
async def get_agent_score_history(
    slug: str,
    window: str = Query("30d", pattern="^(1h|1d|7d|30d|90d|all)$"),
    limit: int = Query(2000, ge=1, le=10_000),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[dict[str, Any]]:
    """Score timeseries for one agent. Used by /compare's overlay chart."""
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    since = _window_to_since(window)
    return await queries.agent_score_history(
        session, agent_id=detail["id"], since=since, limit=limit
    )


@router.get("/{slug}/benchmarks", response_model=list[BenchmarkResultOut])
async def get_agent_benchmarks(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[BenchmarkResultOut]:
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    rows = await queries.benchmarks_for_agent(session, detail["id"])
    return [BenchmarkResultOut(**r) for r in rows]


@router.get("/{slug}/signals.csv")
async def get_agent_signals_csv(
    slug: str,
    window: str = Query("30d", pattern="^(7d|30d|90d|all)$"),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> StreamingResponse:
    """Raw signals as a downloadable CSV. One row per signal reading.

    Columns: source, captured_at (ISO8601), value. The agent's signals
    are the same numbers the scoring service consumes — exporting them
    lets readers verify the score for themselves."""
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    since = _window_to_since(window)
    series = await queries.signals_for_agent(
        session, agent_id=detail["id"], sources=None, since=since, limit=10_000
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["source", "captured_at", "value"])
    for s in series:
        for p in s["points"]:
            writer.writerow(
                [s["source"], p["captured_at"].isoformat(), p["value"]]
            )
    buf.seek(0)
    headers = {
        "Content-Disposition": f'attachment; filename="{slug}-signals-{window}.csv"',
    }
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv", headers=headers
    )


@router.get("/{slug}/similar", response_model=list[SimilarAgent])
async def get_similar_agents(
    slug: str,
    limit: int = Query(10, ge=1, le=50),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[SimilarAgent]:
    detail = await queries.get_agent_by_slug(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")
    rows = await queries.similar_agents(session, agent_id=detail["id"], limit=limit)
    return [SimilarAgent(**r) for r in rows]


def _window_to_since(window: str) -> datetime:
    deltas = {
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    if window == "all":
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime.now(UTC) - deltas.get(window, timedelta(days=30))
