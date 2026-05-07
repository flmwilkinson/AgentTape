"""FastAPI app for the ingestion service container.

The container runs ``uvicorn ingestion.main:app``; the lifespan hook
starts the three-tier scheduler in-process. Set
``INGESTION_SCHEDULER=off`` to launch /health-only (useful for quickly
iterating on the API without the schedulers eating CPU).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis_async
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from ingestion.config import get_settings
from ingestion.db import session_factory
from ingestion.scheduler import build_schedulers
from ingestion.telemetry import init as init_telemetry

init_telemetry("agenttape-ingestion")

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    schedulers: dict[str, Any] = {}
    if os.environ.get("INGESTION_SCHEDULER", "on").lower() != "off":
        schedulers = build_schedulers(get_settings())
        for sched in schedulers.values():
            sched.start()
        log.info("ingestion schedulers started: %s", list(schedulers))
    yield
    for sched in schedulers.values():
        sched.shutdown(wait=False)


app = FastAPI(title="AgentTape Ingestion", version="0.0.0", lifespan=lifespan)


@app.get("/health")
@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}


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
