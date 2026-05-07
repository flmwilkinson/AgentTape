"""Long-running discovery service.

Hosts /health and runs each scout + the promoter on its own APScheduler
job. The CLI (``python -m discovery.run``) is the same code path used
for one-off invocations and tests.

Set ``DISCOVERY_SCHEDULER=off`` to disable the scheduler (useful when
running just the FastAPI part for local dev).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from discovery.config import get_settings
from discovery.db import session_factory
from discovery.promoter import run_promoter
from discovery.scouts import ALL_SCOUTS, Scout
from discovery.telemetry import init as init_telemetry

init_telemetry("agenttape-discovery")

log = logging.getLogger(__name__)


async def _run_scout_job(scout_cls: type[Scout]) -> None:
    scout = scout_cls(get_settings())
    try:
        async with session_factory()() as session:
            await scout.run(session)
    except Exception:  # noqa: BLE001
        log.exception("scout %s failed", scout_cls.name)
    finally:
        await scout.aclose()


async def _promoter_job() -> None:
    try:
        async with session_factory()() as session:
            await run_promoter(session)
    except Exception:  # noqa: BLE001
        log.exception("promoter failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler: AsyncIOScheduler | None = None
    if os.environ.get("DISCOVERY_SCHEDULER", "on").lower() != "off":
        scheduler = AsyncIOScheduler()
        for cls in ALL_SCOUTS:
            scheduler.add_job(
                _run_scout_job,
                IntervalTrigger(seconds=cls.interval_seconds),
                args=[cls],
                id=f"scout-{cls.name}",
                # Stagger first run by 30s so we don't slam every API at boot.
                next_run_time=None,
            )
        scheduler.add_job(
            _promoter_job,
            IntervalTrigger(seconds=10 * 60),
            id="promoter",
        )
        scheduler.start()
        log.info("discovery scheduler started with %d jobs", len(scheduler.get_jobs()))
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AgentTape Discovery", version="0.0.0", lifespan=lifespan)


@app.get("/health")
@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "discovery"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness — Postgres + Redis pings. 503 with detail if either fails."""
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
