"""Cron-style schedule for the things the debouncer doesn't drive.

- Hourly full recompute of every admitted agent's score. Scoring is
  primarily event-driven (the debouncer reacts to ingestion events) but
  some agents — especially foundation models — receive no upstream
  events and would otherwise stay frozen at their admission score.
  An hourly heartbeat ensures every agent has a fresh row, which
  keeps the score-history charts populated.
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

from scoring.compute import all_admitted_agent_ids, recompute_agents
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


async def _heartbeat_recompute_job() -> None:
    """Recompute every admitted agent. Cheap because the population
    stats are computed once per batch, not per agent."""
    settings = get_settings()
    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        async with session_factory()() as session:
            ids = await all_admitted_agent_ids(session)
            out = await recompute_agents(session, ids, redis_client)
            log.info("heartbeat recompute: %s", out)
    except Exception:  # noqa: BLE001
        log.exception("heartbeat recompute job failed")
    finally:
        await redis_client.aclose()


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
        _heartbeat_recompute_job,
        IntervalTrigger(seconds=settings.heartbeat_recompute_seconds),
        id="hourly-recompute",
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
