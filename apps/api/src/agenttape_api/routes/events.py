"""/events — paginated firehose for journalists."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import EventOut, Page

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=Page[EventOut])
async def list_events(
    kind: str | None = Query(
        None,
        description=(
            "Filter by event kind: agent_admitted, score_changed, rank_changed, "
            "index_rebalanced, signal_spike, agent_flagged"
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> Page[EventOut]:
    items, total = await queries.list_events(
        session, kind=kind, limit=limit, offset=offset
    )
    return Page[EventOut](items=items, total=total, limit=limit, offset=offset)
