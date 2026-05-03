"""/tags — taxonomy endpoint with counts."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session

router = APIRouter(prefix="/tags", tags=["tags"])


class TagWithCount(BaseModel):
    kind: str
    value: str
    display_name: str
    count: int


@router.get("", response_model=list[TagWithCount])
async def list_tags(
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[TagWithCount]:
    rows = await queries.list_tags(session)
    return [TagWithCount(**r) for r in rows]
