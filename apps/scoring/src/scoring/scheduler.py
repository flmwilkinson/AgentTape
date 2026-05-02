"""Cron-style schedule for the things the debouncer doesn't drive.

- Hourly snapshot of every index's composite value into ``index_snapshots``.
- Weekly rebalance Mondays 03:00 UTC for every index.

Lives in its own AsyncIOScheduler so its failures are isolated from
the subscriber's event loop.
"""
from __future__ import annotations

import logging

import redis.asyncio as redis_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scoring.config import Settings, get_settings
from scoring.db import session_factory
from scoring.indexes import ensure_indexes, rebalance_all, snapshot_all_indexes

log = logging.getLogger(__name__)


async def _snapshot_job() -> None:
    try:
        async with session_factory()() as session:
            await snapshot_all_indexes(session)
    except Exception:  # noqa: BLE001
        log.exception("snapshot job failed")


async def _rebalance_job() -> None:
    settings = get_settings()
    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        async with session_factory()() as session:
            await ensure_indexes(session)
            await rebalance_all(session, redis_client)
    except Exception:  # noqa: BLE001
        log.exception("rebalance job failed")
    finally:
        await redis_client.aclose()


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60}
    )
    scheduler.add_job(
        _snapshot_job,
        IntervalTrigger(seconds=settings.snapshot_interval_seconds),
        id="hourly-snapshot",
    )
    scheduler.add_job(
        _rebalance_job,
        CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="UTC"),
        id="weekly-rebalance",
    )
    return scheduler
