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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from discovery.config import get_settings
from discovery.db import session_factory
from discovery.promoter import run_promoter
from discovery.scouts import ALL_SCOUTS, Scout

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
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "discovery"}
