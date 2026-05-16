"""Cron-style schedule for the things the debouncer doesn't drive.

- Hourly full recompute of every admitted agent's score. Scoring is
  primarily event-driven (the debouncer reacts to ingestion events) but
  some agents — especially foundation models — receive no upstream
  events and would otherwise stay frozen at their admission score.
  An hourly heartbeat ensures every agent has a fresh row, which
  keeps the score-history charts populated.
- Hourly snapshot of every index's composite value into ``index_snapshots``.
- Weekly rebalance Mondays 03:00 UTC for every index.
- Daily retention cleanup at 04:00 UTC — bounds the append-only
  tables (signals / scores / events) so storage doesn't grow
  unboundedly. See ``_retention_cleanup_job`` for the rules.

Lives in its own AsyncIOScheduler so its failures are isolated from
the subscriber's event loop.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from scoring.compute import all_admitted_agent_ids, recompute_agents
from scoring.config import Settings, get_settings
from scoring.db import engine as get_engine, session_factory
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


# Retention defaults — same numbers the standalone script uses. Kept
# inline so the cron path is self-contained.
SIGNALS_DAYS = 90
SCORES_DAYS = 90
EVENTS_DAYS = 30
CANDIDATES_DAYS = 14


async def _retention_cleanup_job() -> None:
    """Daily retention pass that bounds append-only table growth.

    Rules:
      • signals — drop rows older than SIGNALS_DAYS, except
        ``benchmark_score`` (Quality history matters, low volume).
      • scores — downsample older than SCORES_DAYS to one row per
        agent per day, so the "all" window on the score chart still
        carries a long-term trend line.
      • events — drop rows older than EVENTS_DAYS.
      • discovery_candidates.raw_payload — null out for resolved
        candidates (admitted or rejected) older than CANDIDATES_DAYS,
        keeping the row for audit but dropping the bulky JSONB.

    After the deletes, VACUUM ANALYZE each affected table so Postgres
    actually reclaims the space rather than leaving dead tuples.
    Uses plain VACUUM (not VACUUM FULL) so the cleanup can run while
    the app is live.
    """
    sig_cutoff = datetime.now(UTC) - timedelta(days=SIGNALS_DAYS)
    score_cutoff = datetime.now(UTC) - timedelta(days=SCORES_DAYS)
    event_cutoff = datetime.now(UTC) - timedelta(days=EVENTS_DAYS)
    dc_cutoff = datetime.now(UTC) - timedelta(days=CANDIDATES_DAYS)

    affected: dict[str, int] = {}
    try:
        async with session_factory()() as session:
            for label, sql, params in (
                (
                    "signals",
                    """
                    DELETE FROM signals
                    WHERE captured_at < :cutoff
                      AND source::text != 'benchmark_score'
                    """,
                    {"cutoff": sig_cutoff},
                ),
                (
                    "scores_downsample",
                    """
                    DELETE FROM scores
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY agent_id,
                                                    date_trunc('day', computed_at)
                                       ORDER BY computed_at ASC
                                   ) AS rn
                            FROM scores
                            WHERE computed_at < :cutoff
                        ) ranked
                        WHERE rn > 1
                    )
                    """,
                    {"cutoff": score_cutoff},
                ),
                (
                    "events",
                    "DELETE FROM events WHERE created_at < :cutoff",
                    {"cutoff": event_cutoff},
                ),
                (
                    "discovery_candidates_payload",
                    """
                    UPDATE discovery_candidates
                    SET raw_payload = NULL
                    WHERE raw_payload IS NOT NULL
                      AND found_at < :cutoff
                      AND (
                        promoted_to_agent_id IS NOT NULL
                        OR rejection_reason IS NOT NULL
                      )
                    """,
                    {"cutoff": dc_cutoff},
                ),
            ):
                r = await session.execute(text(sql), params)
                affected[label] = r.rowcount if r.rowcount is not None else -1
            await session.commit()
        log.info("retention deletes: %s", affected)
    except Exception:  # noqa: BLE001
        log.exception("retention deletes failed")
        return

    # VACUUM outside the transaction — Postgres rejects VACUUM inside
    # one. AUTOCOMMIT isolation does the right thing.
    try:
        eng = get_engine()
        async with eng.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            for tbl in ("signals", "scores", "events", "discovery_candidates"):
                try:
                    await conn.execute(text(f"VACUUM ANALYZE {tbl}"))
                except Exception as e:  # noqa: BLE001
                    log.warning("VACUUM %s failed: %s", tbl, e)
        log.info("retention vacuum done")
    except Exception:  # noqa: BLE001
        log.exception("retention vacuum stage failed")


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60}
    )
    # Stagger first fires so the heartbeat and snapshot don't both
    # hit the DB at boot. After their first fire each runs on its
    # interval. Explicit next_run_time is required — APScheduler
    # otherwise waits a full interval before firing once.
    now = datetime.now(UTC)
    scheduler.add_job(
        _heartbeat_recompute_job,
        IntervalTrigger(seconds=settings.heartbeat_recompute_seconds),
        id="hourly-recompute",
        next_run_time=now + timedelta(seconds=20),
    )
    scheduler.add_job(
        _snapshot_job,
        IntervalTrigger(seconds=settings.snapshot_interval_seconds),
        id="hourly-snapshot",
        next_run_time=now + timedelta(seconds=45),
    )
    scheduler.add_job(
        _rebalance_job,
        CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="UTC"),
        id="weekly-rebalance",
    )
    # Daily retention at 04:00 UTC — well after the weekly rebalance
    # (Mondays 03:00) so the two never contend for VACUUM locks. The
    # cleanup deletes are cheap; VACUUM ANALYZE is what takes the
    # real time and we want it to have a clear window.
    scheduler.add_job(
        _retention_cleanup_job,
        CronTrigger(hour=4, minute=0, timezone="UTC"),
        id="daily-retention",
    )
    return scheduler
