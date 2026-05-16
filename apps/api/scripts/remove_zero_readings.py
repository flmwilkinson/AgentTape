"""Remove zero / near-zero artifact rows from signals + scores +
index_snapshots.

Use case: after emergency_cleanup brought the DB back, the first
ingestion sweep + scoring tick + hourly index snapshot wrote rows
based on partially-warm state. Those values are zero or near-zero
and live forever in the time-series tables — visible as 0 spikes
on the score chart and the index composite chart, and (for
signals) as the "latest reading" that gets fed into every
subsequent score recompute until the next sweep replaces them.

What this script DELETEs (default: across all time, all three
tables — every artifact regardless of when):

  • signals          WHERE value = 0
  • scores           WHERE agent_score IS NULL OR agent_score < 1.0
  • index_snapshots  WHERE composite_value < 1.0

Optionally narrow to a time window with --from / --to. Optionally
restrict to one table with --signals-only / --scores-only /
--snapshots-only.

Why these thresholds are safe:

  • A signal value of exactly 0 for an admitted agent is almost
    always an artifact. Many "mention count" signals can legitimately
    be 0, but we never use those legitimate zeros — the pillar mean
    just skips them via dedupe-on-insert next tick.
  • A score < 1.0 is mathematically impossible for any healthy
    agent — even a single-pillar 1-signal agent at scaled value 1
    produces 0.40 × 1 = 0.4 (Adoption application), so we use < 1.0
    to give a small safety margin while still catching the
    all-pillars-collapsed-to-zero artifact case.
  • A legitimate index composite is ≥ ~30 (the average of admitted
    agents' scores). < 1.0 is unambiguously artifact territory.

Dry-run by default; --commit to actually delete. Each delete in its
own transaction so a failure on one table doesn't roll back the
others.

Usage:
    # Delete every artifact zero in the whole DB:
    python -m scripts.remove_zero_readings --commit

    # Or restrict to a window:
    python -m scripts.remove_zero_readings \\
        --from "2026-05-16 10:30:00+00" \\
        --to   "2026-05-16 12:00:00+00" \\
        --commit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("remove_zero_readings")


def _engine_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    parts = urlsplit(url)
    drop = {"sslmode", "channel_binding"}
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in drop]
    return urlunsplit(parts._replace(query=urlencode(qs)))


def _time_clause(col: str, args: argparse.Namespace) -> tuple[str, dict]:
    """Build an optional time filter. Returns (sql_fragment, params)."""
    clauses: list[str] = []
    params: dict = {}
    if args.from_time is not None:
        clauses.append(f"{col} >= :from_t")
        params["from_t"] = args.from_time
    if args.to_time is not None:
        clauses.append(f"{col} <= :to_t")
        params["to_t"] = args.to_time
    if not clauses:
        return "", {}
    return " AND " + " AND ".join(clauses), params


async def main(args: argparse.Namespace) -> None:
    engine = create_async_engine(_engine_url(), echo=False)

    if args.from_time or args.to_time:
        log.info("time window: %s → %s", args.from_time, args.to_time)
    else:
        log.info("time window: (none — applies to all time)")

    do_signals = not (args.scores_only or args.snapshots_only)
    do_scores = not (args.signals_only or args.snapshots_only)
    do_snapshots = not (args.signals_only or args.scores_only)

    # Preview counts.
    async with engine.connect() as conn:
        sig_count = 0
        score_count = 0
        snap_count = 0

        if do_signals:
            extra, params = _time_clause("captured_at", args)
            sig_count = (
                await conn.execute(
                    text(
                        f"SELECT count(*) FROM signals "
                        f"WHERE value = 0 {extra}"
                    ),
                    params,
                )
            ).scalar_one()
        if do_scores:
            extra, params = _time_clause("computed_at", args)
            score_count = (
                await conn.execute(
                    text(
                        f"SELECT count(*) FROM scores "
                        f"WHERE (agent_score IS NULL OR agent_score < 1.0) "
                        f"{extra}"
                    ),
                    params,
                )
            ).scalar_one()
        if do_snapshots:
            extra, params = _time_clause("captured_at", args)
            snap_count = (
                await conn.execute(
                    text(
                        f"SELECT count(*) FROM index_snapshots "
                        f"WHERE composite_value < 1.0 {extra}"
                    ),
                    params,
                )
            ).scalar_one()

    log.info(
        "would affect: signals=%s, scores=%s, index_snapshots=%s",
        f"{sig_count:,}" if do_signals else "(skipped)",
        f"{score_count:,}" if do_scores else "(skipped)",
        f"{snap_count:,}" if do_snapshots else "(skipped)",
    )

    if not args.commit:
        log.info("dry-run — nothing changed. Re-run with --commit to delete.")
        return

    # Each DELETE in its own committed transaction.
    if do_signals:
        extra, params = _time_clause("captured_at", args)
        async with engine.begin() as conn:
            r = await conn.execute(
                text(f"DELETE FROM signals WHERE value = 0 {extra}"),
                params,
            )
        log.info("signals: deleted %s rows", r.rowcount)

    if do_scores:
        extra, params = _time_clause("computed_at", args)
        async with engine.begin() as conn:
            r = await conn.execute(
                text(
                    f"DELETE FROM scores "
                    f"WHERE (agent_score IS NULL OR agent_score < 1.0) "
                    f"{extra}"
                ),
                params,
            )
        log.info("scores: deleted %s rows", r.rowcount)

    if do_snapshots:
        extra, params = _time_clause("captured_at", args)
        async with engine.begin() as conn:
            r = await conn.execute(
                text(
                    f"DELETE FROM index_snapshots "
                    f"WHERE composite_value < 1.0 {extra}"
                ),
                params,
            )
        log.info("index_snapshots: deleted %s rows", r.rowcount)

    log.info(
        "done. Next ingestion / scoring / snapshot ticks will write "
        "fresh values; the artifacts won't reappear thanks to dedupe-"
        "on-insert."
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Remove zero / near-zero artifact rows from time-series tables."
    )
    p.add_argument(
        "--from", dest="from_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Optional start of time window, ISO format. Default: no lower bound.",
    )
    p.add_argument(
        "--to", dest="to_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Optional end of time window, ISO format. Default: no upper bound.",
    )
    p.add_argument(
        "--signals-only", action="store_true",
        help="Only delete from signals (skip scores + index_snapshots).",
    )
    p.add_argument(
        "--scores-only", action="store_true",
        help="Only delete from scores (skip signals + index_snapshots).",
    )
    p.add_argument(
        "--snapshots-only", action="store_true",
        help="Only delete from index_snapshots (skip signals + scores).",
    )
    p.add_argument(
        "--commit", action="store_true",
        help="Actually delete. Default is dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
