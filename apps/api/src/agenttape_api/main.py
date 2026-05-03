from __future__ import annotations

import logging
import os
from typing import Any

import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from agenttape_api.db.session import session_factory
from agenttape_api.routes import ROUTERS

log = logging.getLogger(__name__)

app = FastAPI(
    title="AgentTape API",
    version="0.0.0",
    description=(
        "Read API for the AgentTape live AI-agent index. Every score on the "
        "wire is an envelope — headline + four pillars + manipulation_resistance. "
        "There is no headline-only path."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

for router in ROUTERS:
    app.include_router(router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "agenttape-api", "docs": "/docs"}


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — the process is alive. Always returns 200 if reachable."""
    return {"status": "ok", "service": "api"}


@app.get("/ready", tags=["meta"])
async def ready() -> dict[str, Any]:
    """Readiness — Postgres + Redis pings. Returns 503 with detail if either fails."""
    checks: dict[str, Any] = {"db": False, "redis": False}
    db_err: str | None = None
    redis_err: str | None = None

    try:
        async with session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception as e:  # noqa: BLE001
        db_err = str(e)

    try:
        client = redis_async.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await client.ping()
        await client.aclose()
        checks["redis"] = True
    except Exception as e:  # noqa: BLE001
        redis_err = str(e)

    if all(checks.values()):
        return {"status": "ready", **checks}
    from fastapi import HTTPException

    raise HTTPException(
        status_code=503,
        detail={
            "status": "not_ready",
            **checks,
            "db_error": db_err,
            "redis_error": redis_err,
        },
    )
