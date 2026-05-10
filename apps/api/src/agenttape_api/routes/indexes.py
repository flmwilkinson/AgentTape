"""/indexes endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import (
    IndexDetail,
    IndexSnapshotOut,
    IndexSummary,
    RebalanceOut,
)

router = APIRouter(prefix="/indexes", tags=["indexes"])


@router.get("", response_model=list[IndexSummary])
async def list_indexes(
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[IndexSummary]:
    rows = await queries.list_indexes(session)
    return [IndexSummary(**r) for r in rows]


# All-indexes history in one round-trip. Declared BEFORE /{slug}
# so /indexes/histories doesn't match the slug-pattern route below.
@router.get("/histories", response_model=dict[str, list[IndexSnapshotOut]])
async def get_all_index_histories(
    window: str = Query("30d", pattern="^(1d|7d|30d|90d|all)$"),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> dict[str, list[IndexSnapshotOut]]:
    """Returns ``{ slug: [snapshots] }`` for every index in one query.

    The Floor's index card grid uses this to draw 6 sparklines —
    fetching them as N parallel /indexes/{slug}/history calls cost
    N round-trips of connection+query setup. One query, one
    round-trip, dictionary keyed by slug for direct lookup on the
    client.
    """
    grouped = await queries.index_history_all(
        session, since=_window_to_since(window)
    )
    return {
        slug: [IndexSnapshotOut(**r) for r in rows]
        for slug, rows in grouped.items()
    }


@router.get("/{slug}", response_model=IndexDetail)
async def get_index(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> IndexDetail:
    detail = await queries.get_index_detail(session, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"index {slug!r} not found")
    return IndexDetail(**detail)


@router.get("/{slug}/history", response_model=list[IndexSnapshotOut])
async def get_index_history(
    slug: str,
    window: str = Query("30d", pattern="^(1d|7d|30d|90d|all)$"),
    limit: int = Query(2000, ge=1, le=10_000),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[IndexSnapshotOut]:
    rows = await queries.index_history(
        session, slug=slug, since=_window_to_since(window), limit=limit
    )
    return [IndexSnapshotOut(**r) for r in rows]


@router.get("/{slug}/rebalances", response_model=list[RebalanceOut])
async def get_index_rebalances(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[RebalanceOut]:
    rows = await queries.index_rebalances(session, slug=slug, limit=limit)
    return [RebalanceOut(**r) for r in rows]


def _window_to_since(window: str) -> datetime:
    deltas = {
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    if window == "all":
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime.now(UTC) - deltas.get(window, timedelta(days=30))
