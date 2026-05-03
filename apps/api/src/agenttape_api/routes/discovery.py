"""/discovery/recent — the launch-wire view of newly-admitted agents."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import AgentSummary

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/recent", response_model=list[AgentSummary])
async def recent_admissions(
    limit: int = Query(50, ge=1, le=200),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[AgentSummary]:
    rows = await queries.recent_admissions(session, limit=limit)
    return [AgentSummary(**r) for r in rows]
