"""/search endpoint — facet + vibe (embedding) search."""
from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api import queries
from agenttape_api.deps import get_session
from agenttape_api.schemas import SearchHit, SearchResult

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=20),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> list[dict]:
    """Fast prefix-prioritised autocomplete. Returns name+slug+kind only."""
    return await queries.search_suggest(session, q=q, limit=limit)


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    mode: str = Query("text", pattern="^(text|vibe)$"),
    limit: int = Query(20, ge=1, le=100),
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> SearchResult:
    if mode == "vibe":
        embedding = await _embed(q)
        if embedding is None:
            # No embedding provider configured — fall back to text search
            # rather than a 500. The API stays usable in dev.
            hits = await queries.text_search(session, q=q, limit=limit)
        else:
            hits = await queries.vibe_search(session, embedding=embedding, limit=limit)
    else:
        hits = await queries.text_search(session, q=q, limit=limit)
    facets = await queries.facet_counts(session)
    return SearchResult(
        hits=[SearchHit(**h) for h in hits],
        facets={k: [{"value": v["value"], "count": v["count"]} for v in vs] for k, vs in facets.items()},
    )


async def _embed(query: str) -> list[float] | None:
    """Best-effort Voyage AI call. Returns None when no API key is set."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"input": [query[:4000]], "model": "voyage-3"},
            )
            r.raise_for_status()
            vec = r.json()["data"][0]["embedding"]
            if len(vec) < 1536:
                vec = vec + [0.0] * (1536 - len(vec))
            return vec[:1536]
    except Exception:  # noqa: BLE001
        return None
