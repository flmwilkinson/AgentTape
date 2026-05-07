from __future__ import annotations

import logging
import os
from typing import Any

import redis.asyncio as redis_async
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from agenttape_api.db.session import session_factory
from agenttape_api.rate_limit import limiter, public_rate_limit
from agenttape_api.routes import ROUTERS
from agenttape_api.telemetry import init as init_telemetry

# Boot telemetry as soon as the module is imported — uvicorn imports
# main.py before opening the socket, so traces cover the first request.
init_telemetry("agenttape-api")

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
    allow_headers=["*", "x-api-key"],
)

# Rate limiting: 60 rpm anon / 600 rpm with X-API-Key. The middleware
# applies the limit to every route; routes that need stricter limits
# can decorate themselves with @limiter.limit(...).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def attach_rate_limit(request: Request, call_next):
    # slowapi looks for ``request.state.view_rate_limit`` (a string like
    # "60/minute") to decide which bucket to count against. Setting it
    # per-request lets us key auth vs anon off the X-API-Key header.
    request.state.view_rate_limit = public_rate_limit(request)
    return await call_next(request)


for router in ROUTERS:
    app.include_router(router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "agenttape-api", "docs": "/docs"}


@app.get("/health", tags=["meta"])
@app.get("/healthz", tags=["meta"])
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
