"""Retention cleanup — bound the append-only tables' growth.

Default windows (override via env or --signals-days etc.):

    signals          90 days   (except benchmark_score — kept forever
                                 because Quality history matters)
    scores            90 days   (downsampled: keep 1 row per agent
                                  per day for older rows)
    events            30 days
    discovery_candidates.raw_payload   14 days after promotion/rejection
                                        (we keep the row, just null the
                                         bulky JSONB column)

After the deletes, runs VACUUM on each affected table so Postgres
actually reclaims the space rather than leaving dead tuples behind.

Read-only dry-run by default (``--dry-run`` flag is the default). Pass
``--commit`` to actually delete. Either way, prints what would be /
was removed per table.

Run inside the API container:

    docker compose -f infra/cloud/docker-compose.cloud.yml exec api \\
        python -m scripts.retention_cleanup --commit

Schedule: drop the same command into a daily cron once you've
verified the first run looked right. See the scoring scheduler
notes for how that wires in.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("retention_cleanup")


async def _engine_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts = urlsplit(url)
    drop = {"sslmode", "channel_binding"}
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in drop]
    return urlunsplit(parts._replace(query=urlencode(qs)))


async def main(args: argparse.Namespace) -> None:
    url = await _engine_url()
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    sig_cutoff = datetime.now(UTC) - timedelta(days=args.signals_days)
    score_cutoff = datetime.now(UTC) - timedelta(days=args.scores_days)
    event_cutoff = datetime.now(UTC) - timedelta(days=args.events_days)
    dc_cutoff = datetime.now(UTC) - timedelta(days=args.candidates_days)

    log.info(
        "retention plan: signals<%s, scores<%s, events<%s, dc.raw_payload<%s, commit=%s",
        sig_cutoff.date(),
        score_cutoff.date(),
        event_cutoff.date(),
        dc_cutoff.date(),
        args.commit,
    )

    # We hold one session per phase so a failure on (say) scores
    # doesn't roll back the signals delete.
    async def run_phase(label: str, sql: str, params: dict) -> int:
        async with Session() as session:
            # COUNT preview, then DELETE if --commit.
            preview_sql = (
                "SELECT count(*) FROM (" + sql.replace(
                    "DELETE FROM", "SELECT 1 FROM"
                ) + ") AS preview"
            ) if sql.strip().upper().startswith("DELETE") else None
            if preview_sql:
                try:
                    n = (await session.execute(text(preview_sql), params)).scalar_one()
                except Exception:  # noqa: BLE001
                    # The SELECT rewrite is best-effort; if it fails just
                    # log that we couldn't preview.
                    n = -1
            else:
                n = -1

            if not args.commit:
                log.info("[dry-run] %s: would affect %s rows", label, n)
                return 0

            r = await session.execute(text(sql), params)
            await session.commit()
            affected = r.rowcount if r.rowcount is not None else -1
            log.info("%s: affected %s rows", label, affected)
            return affected

    # --- signals --------------------------------------------------------
    # Keep benchmark_score forever — that table powers the Quality pillar
    # and the agent's benchmark history chart; the volume is low so the
    # cost is negligible.
    await run_phase(
        "signals (non-benchmark, > N days)",
        """
        DELETE FROM signals
        WHERE captured_at < :cutoff
          AND source::text != 'benchmark_score'
        """,
        {"cutoff": sig_cutoff},
    )

    # --- scores ---------------------------------------------------------
    # Old scores are downsampled to one row per agent per day rather
    # than deleted outright, so the "all" window on the score chart
    # still has a long-term trend line. The downsampling uses a window
    # function to keep the first score of each (agent_id, day) pair
    # before the cutoff.
    await run_phase(
        "scores (downsample > N days to one row per agent per day)",
        """
        DELETE FROM scores
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY agent_id, date_trunc('day', computed_at)
                           ORDER BY computed_at ASC
                       ) AS rn
                FROM scores
                WHERE computed_at < :cutoff
            ) ranked
            WHERE rn > 1
        )
        """,
        {"cutoff": score_cutoff},
    )

    # --- events ---------------------------------------------------------
    await run_phase(
        "events (> N days)",
        "DELETE FROM events WHERE created_at < :cutoff",
        {"cutoff": event_cutoff},
    )

    # --- discovery_candidates.raw_payload -------------------------------
    # Keep the candidate row (audit trail) but drop the heavy JSONB
    # once the candidate has resolved one way or the other and the
    # row is older than the cutoff. promoted_to_agent_id IS NOT NULL
    # means admitted, rejection_reason IS NOT NULL means rejected,
    # found_at is the original timestamp.
    await run_phase(
        "discovery_candidates.raw_payload (resolved + > N days)",
        """
        UPDATE discovery_candidates
        SET raw_payload = NULL
        WHERE raw_payload IS NOT NULL
          AND found_at < :cutoff
          AND (promoted_to_agent_id IS NOT NULL OR rejection_reason IS NOT NULL)
        """,
        {"cutoff": dc_cutoff},
    )

    # --- VACUUM ---------------------------------------------------------
    # Postgres won't reclaim the disk back to free space until the
    # dead tuples from the DELETEs are vacuumed. We run VACUUM (not
    # VACUUM FULL — that takes an exclusive lock and rewrites the
    # whole table) so the cleanup can run while the app is live.
    if args.commit:
        async with engine.connect() as conn:
            # VACUUM cannot run inside a transaction.
            await conn.execute(text("COMMIT"))
            for tbl in ("signals", "scores", "events", "discovery_candidates"):
                try:
                    await conn.execute(text(f"VACUUM ANALYZE {tbl}"))
                    log.info("VACUUM ANALYZE %s ok", tbl)
                except Exception as e:  # noqa: BLE001
                    log.warning("VACUUM %s failed: %s", tbl, e)

    log.info("retention_cleanup done (commit=%s)", args.commit)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Retention cleanup for AgentTape DB.")
    p.add_argument(
        "--signals-days", type=int, default=90,
        help="Delete non-benchmark signals older than this many days (default 90).",
    )
    p.add_argument(
        "--scores-days", type=int, default=90,
        help="Downsample scores older than this many days to one row per agent per day (default 90).",
    )
    p.add_argument(
        "--events-days", type=int, default=30,
        help="Delete events older than this many days (default 30).",
    )
    p.add_argument(
        "--candidates-days", type=int, default=14,
        help="Null out raw_payload on resolved candidates older than this many days (default 14).",
    )
    p.add_argument(
        "--commit", action="store_true",
        help="Actually run the deletes + VACUUM. Default is dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
