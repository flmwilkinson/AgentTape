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
    capability: str | None = Query(None, max_length=64),
    deployment: str | None = Query(None, max_length=64),
    entity_kind: str | None = Query(
        None, pattern="^(application|foundation_model|framework|mcp_server)$"
    ),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[MoverOut]:
    rows = await queries.movers(
        session,
        window=window,
        limit=limit,
        capability=capability,
        deployment=deployment,
        entity_kind=entity_kind,
    )
    return [MoverOut(**r) for r in rows]
