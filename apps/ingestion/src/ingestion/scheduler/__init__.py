"""Three independent APScheduler instances — one per tier.

Why three schedulers and not one with three jobs:
- Independent failure: a stuck SLOW benchmark scrape can't tie up the
  thread pool serving FAST.
- Independent backpressure: each scheduler has its own ``misfire_grace_time``
  and ``max_instances``, so we can be lenient on SLOW without making
  FAST ticks pile up if the loop slips.
- Independent observability: per-tier logs and per-tier ``running``
  state cleanly mapped to a /status endpoint later.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ingestion.config import Settings, get_settings
from ingestion.db import session_factory
from ingestion.integrity import run_integrity_checks
from ingestion.sources.base import Ingestor, load_admitted_agents, open_redis
from ingestion.tiers import FAST, MEDIUM, SLOW, TierName

log = logging.getLogger(__name__)


async def run_tier(
    settings: Settings, tier_name: str, ingestor_classes: list[type[Ingestor]]
) -> dict[str, Any]:
    """One pass of every ingestor in a tier; runs them in parallel."""
    log.info("tier %s tick starting", tier_name)
    redis_client = await open_redis(settings)
    results: list[dict[str, Any]] = []
    try:
        async with session_factory()() as session:
            agents = await load_admitted_agents(session)
        if not agents:
            log.info("tier %s: no admitted agents yet, skipping", tier_name)
            return {"tier": tier_name, "agents": 0, "ingestors": []}

        ingestors = [cls(settings) for cls in ingestor_classes]
        try:
            async def run_one(ing: Ingestor) -> dict[str, Any]:
                async with session_factory()() as session:
                    stats = await ing.run(session, agents, redis_client)
                return {"ingestor": ing.name, **stats}

            results = await asyncio.gather(
                *(run_one(ing) for ing in ingestors), return_exceptions=False
            )
        finally:
            for ing in ingestors:
                await ing.aclose()

        # Manipulation checks run on the medium tier — by then we have
        # both fast (stars/HN) and medium (contributors/HF) data points.
        if tier_name == TierName.MEDIUM:
            async with session_factory()() as session:
                integrity = await run_integrity_checks(session, redis_client, settings)
            results.append({"integrity": integrity})

        log.info("tier %s tick done: %d agents, %d ingestors", tier_name, len(agents), len(ingestor_classes))
        return {"tier": tier_name, "agents": len(agents), "ingestors": results}
    finally:
        try:
            await redis_client.aclose()
        except Exception:  # noqa: BLE001
            pass


def build_schedulers(settings: Settings | None = None) -> dict[str, AsyncIOScheduler]:
    """One AsyncIOScheduler per tier. Caller is responsible for start/stop."""
    settings = settings or get_settings()
    schedulers: dict[str, AsyncIOScheduler] = {}

    plan = (
        (TierName.FAST, FAST, settings.fast_tier_seconds),
        (TierName.MEDIUM, MEDIUM, settings.medium_tier_seconds),
        (TierName.SLOW, SLOW, settings.slow_tier_seconds),
    )
    # First fire offsets stagger the tiers so they don't all hammer
    # the DB at once on startup. FAST runs ~10 s after boot, MEDIUM
    # ~30 s, SLOW ~60 s. After the first fire each tier ticks on its
    # own interval. Without an explicit next_run_time, APScheduler
    # waits a full interval before the first run — that's why a
    # 5-minute FAST tier still wouldn't have ticked an hour later.
    first_fire_offsets = {
        TierName.FAST: 10,
        TierName.MEDIUM: 30,
        TierName.SLOW: 60,
    }
    now = datetime.now(UTC)
    for tier_name, classes, interval in plan:
        sched = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,        # squash backlog if we fall behind
                "max_instances": 1,      # never let two ticks of one tier overlap
                "misfire_grace_time": max(30, interval // 2),
            },
        )
        sched.add_job(
            run_tier,
            IntervalTrigger(seconds=interval),
            args=[settings, tier_name, classes],
            id=f"tier-{tier_name}",
            next_run_time=now + timedelta(seconds=first_fire_offsets[tier_name]),
        )
        schedulers[tier_name] = sched
    return schedulers
