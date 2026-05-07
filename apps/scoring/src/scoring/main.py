"""FastAPI app for the scoring service container.

The container runs ``uvicorn scoring.main:app``. The lifespan hook starts:

    - the Redis subscriber (marks agents dirty)
    - the debouncer ticker (flushes once every recompute_debounce_seconds)
    - the APScheduler with the hourly snapshot + Monday 03:00 UTC rebalance

Set ``SCORING_RUNNERS=off`` to start /health-only (useful when iterating
on the API without burning Redis quota).
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis_async
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from scoring.config import get_settings
from scoring.db import session_factory
from scoring.debouncer import get_debouncer
from scoring.indexes import ensure_indexes
from scoring.scheduler import build_scheduler
from scoring.subscriber import run_subscriber
from scoring.telemetry import init as init_telemetry

init_telemetry("agenttape-scoring")

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task[Any]] = []
    scheduler = None
    redis_client: Any = None

    if os.environ.get("SCORING_RUNNERS", "on").lower() != "off":
        settings = get_settings()
        async with session_factory()() as session:
            await ensure_indexes(session)

        debouncer = get_debouncer()
        redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)

        tasks.append(asyncio.create_task(run_subscriber(debouncer, settings)))
        tasks.append(asyncio.create_task(debouncer.run(redis_client)))

        scheduler = build_scheduler(settings)
        scheduler.start()
        log.info("scoring runners started: subscriber + debouncer + scheduler")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    if redis_client is not None:
        await redis_client.aclose()


app = FastAPI(title="AgentTape Scoring", version="0.0.0", lifespan=lifespan)


@app.get("/health")
@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "scoring"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    checks: dict[str, Any] = {"db": False, "redis": False}
    db_err = redis_err = None
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
    raise HTTPException(
        status_code=503,
        detail={"status": "not_ready", **checks, "db_error": db_err, "redis_error": redis_err},
    )
