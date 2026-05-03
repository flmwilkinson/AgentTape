"""/movers endpoint."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import MoverOut

router = APIRouter(prefix="/movers", tags=["movers"])


@router.get("", response_model=list[MoverOut])
async def get_movers(
    window: str = Query("1d", pattern="^(1h|1d|7d|30d)$"),
    limit: int = Query(50, ge=1, le=200),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[MoverOut]:
    rows = await queries.movers(session, window=window, limit=limit)
    return [MoverOut(**r) for r in rows]
