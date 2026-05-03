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
