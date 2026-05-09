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
from datetime import UTC, datetime, timedelta
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
        # APScheduler bug fix: passing ``next_run_time=None`` to
        # ``add_job`` PAUSES the job indefinitely; the comment that
        # used to live here ("stagger first run by 30s") was wrong.
        # The IntervalTrigger then has nothing to compute from and the
        # scout never fires. Symptom in production was no admissions
        # since cloud bootstrap. Now we set an explicit first-run
        # 30 seconds after boot, staggered 15s per scout so we don't
        # slam every external API at the same instant.
        first_run_base = datetime.now(UTC) + timedelta(seconds=30)
        for idx, cls in enumerate(ALL_SCOUTS):
            scheduler.add_job(
                _run_scout_job,
                IntervalTrigger(seconds=cls.interval_seconds),
                args=[cls],
                id=f"scout-{cls.name}",
                next_run_time=first_run_base + timedelta(seconds=idx * 15),
            )
        scheduler.add_job(
            _promoter_job,
            IntervalTrigger(seconds=10 * 60),
            id="promoter",
            # First promoter run 60s after boot — gives the first
            # scout tier a chance to actually drop candidates in.
            next_run_time=datetime.now(UTC) + timedelta(seconds=60),
        )
        scheduler.start()
        scheduled = scheduler.get_jobs()
        log.info(
            "discovery scheduler started with %d jobs; first scout fires at %s",
            len(scheduled),
            first_run_base.isoformat(),
        )
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
