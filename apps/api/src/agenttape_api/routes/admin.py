"""/admin status page.

HTTP Basic auth gated. Returns the operational view of the system —
the page the on-call engineer pulls up first when something looks off.

Auth: ``ADMIN_USER`` / ``ADMIN_PASSWORD`` env vars. If unset, the page
is disabled and returns 503; we fail-closed because a public /admin
would be a great target for scraping.

Metrics:
    - admitted_agents      count of agents.eligibility_status='admitted'
    - candidates_pending   count of discovery_candidates rows still in
                           the "pending review" grey zone
    - last_signal_per_source  most recent signal captured_at per source
                              (proxy for "last successful ingestor run")
    - last_rebalance_per_index  per-index latest run_at
    - ws_connections       fetched from realtime's /admin/stats
    - redis_lag_ms         server-side ping latency
"""
from __future__ import annotations

import asyncio
import os
import secrets
import time
from typing import Annotated, Any

import httpx
import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agenttape_api.deps import get_session

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()


def _check_basic(creds: Annotated[HTTPBasicCredentials, Depends(security)]) -> None:
    user = os.environ.get("ADMIN_USER")
    pw = os.environ.get("ADMIN_PASSWORD")
    if not user or not pw:
        raise HTTPException(
            status_code=503,
            detail="admin disabled — set ADMIN_USER / ADMIN_PASSWORD",
        )
    # Constant-time compares so we don't leak the user/password length.
    ok_user = secrets.compare_digest(creds.username.encode(), user.encode())
    ok_pw = secrets.compare_digest(creds.password.encode(), pw.encode())
    if not (ok_user and ok_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/status")
async def status_page(
    _: Annotated[None, Depends(_check_basic)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    admitted, pending = await asyncio.gather(
        _admitted_count(session),
        _pending_review_count(session),
    )
    last_signals, last_rebalances, ws, redis_lag = await asyncio.gather(
        _last_signal_per_source(session),
        _last_rebalance_per_index(session),
        _ws_connections(),
        _redis_ping_ms(),
    )
    return {
        "admitted_agents": admitted,
        "candidates_pending_review": pending,
        "last_signal_per_source": last_signals,
        "last_rebalance_per_index": last_rebalances,
        "ws_connections": ws,
        "redis_lag_ms": redis_lag,
    }


# ---------------------------------------------------------------- queries


async def _admitted_count(session: AsyncSession) -> int:
    r = await session.execute(
        text("SELECT count(*) FROM agents WHERE eligibility_status = 'admitted'")
    )
    return int(r.scalar_one())


async def _pending_review_count(session: AsyncSession) -> int:
    r = await session.execute(
        text(
            """
            SELECT count(*) FROM discovery_candidates
            WHERE promoted_to_agent_id IS NULL
              AND rejection_reason IS NULL
            """
        )
    )
    return int(r.scalar_one())


async def _last_signal_per_source(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT source, max(captured_at) AS last_at, count(*) AS n_in_last_hour
            FROM signals
            WHERE captured_at > now() - interval '1 hour'
            GROUP BY source
            ORDER BY 1
            """
        )
    )
    return [
        {
            "source": r.source,
            "last_at": r.last_at.isoformat() if r.last_at else None,
            "count_last_hour": int(r.n_in_last_hour),
        }
        for r in rows
    ]


async def _last_rebalance_per_index(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT i.slug, max(r.run_at) AS last_at, count(r.id) AS total
            FROM indexes i
            LEFT JOIN rebalances r ON r.index_id = i.id
            GROUP BY i.slug
            ORDER BY i.slug
            """
        )
    )
    return [
        {
            "index": r.slug,
            "last_at": r.last_at.isoformat() if r.last_at else None,
            "total_rebalances": int(r.total),
        }
        for r in rows
    ]


async def _ws_connections() -> dict[str, Any]:
    """Scrape the realtime service's /admin/stats endpoint."""
    base = os.environ.get("REALTIME_INTERNAL_URL", "http://realtime:8002")
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            r = await http.get(f"{base}/admin/stats")
            r.raise_for_status()
            return r.json().get("connections") or {}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


async def _redis_ping_ms() -> float | None:
    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    try:
        client = redis_async.from_url(
            url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        t0 = time.perf_counter()
        await client.ping()
        dt = (time.perf_counter() - t0) * 1000
        await client.aclose()
        return round(dt, 2)
    except Exception:  # noqa: BLE001
        return None
