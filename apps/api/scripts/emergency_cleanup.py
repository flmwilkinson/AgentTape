"""Emergency cleanup — collapse the append-only tables to a sane
size when the regular retention rules can't help.

When everything is freshly written (data younger than the 90-day
retention floor) and the disk is too full for VACUUM to run, this
script is the way out. It uses TRUNCATE rather than DELETE so
Postgres frees the disk pages immediately, no VACUUM needed.

What it does:

  * signals — keep only the most-recent reading per
    (agent_id, source). 1.1M rows → ~10-15K. Signal values are
    point-in-time snapshots; the per-5-minute history was the bulk
    of the storage waste.

  * scores — keep only the most-recent row per agent_id.
    ~890K rows → ~700. The trend chart goes sparse for now;
    dedupe-on-insert (shipped alongside) means future scores only
    land when the value actually changes, so history rebuilds at
    a sensible rate within days.

  * events — keep the last 3 days only.

Combined effect: frees ~430 MB so the Neon free tier has months of
headroom even with default growth rates.

Two-phase TRUNCATE+restore so the script can run even when disk is
full: phase 1 collapses signals (small temp table, fits in the
current headroom and frees the bulk of the storage) before phase 2
touches scores (which needs a bigger temp table that only fits
*after* phase 1's truncate has freed space).

DESTRUCTIVE. Run with --commit explicitly. Dry-run prints what
would change.

    docker compose -f infra/cloud/docker-compose.cloud.yml exec api \\
        python -m scripts.emergency_cleanup --commit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("emergency_cleanup")


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


async def main(args: argparse.Namespace) -> None:
    engine = create_async_engine(_engine_url(), echo=False)

    # Before-counts so the output shows exactly what we collapsed.
    async with engine.connect() as conn:
        before_signals = (
            await conn.execute(text("SELECT count(*) FROM signals"))
        ).scalar_one()
        before_scores = (
            await conn.execute(text("SELECT count(*) FROM scores"))
        ).scalar_one()
        before_events = (
            await conn.execute(text("SELECT count(*) FROM events"))
        ).scalar_one()

    log.info(
        "before: signals=%s, scores=%s, events=%s",
        f"{before_signals:,}",
        f"{before_scores:,}",
        f"{before_events:,}",
    )

    if not args.commit:
        log.info("dry-run — nothing changed. Re-run with --commit to execute.")
        return

    # All deletes inside one transaction per table so a failure rolls
    # back cleanly. TRUNCATE doesn't need VACUUM to free space —
    # that's the whole point of using it here.
    #
    # The pattern is: copy the rows we want to keep into a temp
    # table, TRUNCATE the source, INSERT from temp back, drop temp.
    # Temp tables live in pg_temp and disappear on session close, so
    # we don't add to disk pressure.

    async with engine.begin() as conn:
        log.info("phase 1/3: collapsing signals → latest-per-(agent,source)")
        await conn.execute(
            text(
                """
                CREATE TEMP TABLE signals_keep ON COMMIT DROP AS
                SELECT DISTINCT ON (agent_id, source) *
                FROM signals
                ORDER BY agent_id, source, captured_at DESC
                """
            )
        )
        kept_signals = (
            await conn.execute(text("SELECT count(*) FROM signals_keep"))
        ).scalar_one()
        log.info("  signals_keep populated: %s rows", f"{kept_signals:,}")
        # TRUNCATE on a partitioned parent truncates all partitions.
        await conn.execute(text("TRUNCATE signals"))
        await conn.execute(
            text("INSERT INTO signals SELECT * FROM signals_keep")
        )
        log.info("  signals collapsed.")

    async with engine.begin() as conn:
        log.info("phase 2/3: collapsing scores → latest-per-agent")
        await conn.execute(
            text(
                """
                CREATE TEMP TABLE scores_keep ON COMMIT DROP AS
                SELECT DISTINCT ON (agent_id) *
                FROM scores
                ORDER BY agent_id, computed_at DESC
                """
            )
        )
        kept_scores = (
            await conn.execute(text("SELECT count(*) FROM scores_keep"))
        ).scalar_one()
        log.info("  scores_keep populated: %s rows", f"{kept_scores:,}")
        await conn.execute(text("TRUNCATE scores"))
        await conn.execute(
            text("INSERT INTO scores SELECT * FROM scores_keep")
        )
        log.info("  scores collapsed.")

    async with engine.begin() as conn:
        log.info("phase 3/3: trimming events to last 3 days")
        r = await conn.execute(
            text(
                "DELETE FROM events WHERE created_at < now() - interval '3 days'"
            )
        )
        log.info("  events deleted: %s", r.rowcount)

    # VACUUM to release dead tuples back to the OS. The signals and
    # scores tables were TRUNCATE'd which already releases pages, but
    # events was DELETE'd so it still needs vacuuming. Now that we
    # have space, this works.
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for tbl in ("signals", "scores", "events", "discovery_candidates"):
            try:
                await conn.execute(text(f"VACUUM ANALYZE {tbl}"))
                log.info("VACUUM ANALYZE %s ok", tbl)
            except Exception as e:  # noqa: BLE001
                log.warning("VACUUM %s failed: %s", tbl, e)

    # After-counts so the output shows the result.
    async with engine.connect() as conn:
        after_signals = (
            await conn.execute(text("SELECT count(*) FROM signals"))
        ).scalar_one()
        after_scores = (
            await conn.execute(text("SELECT count(*) FROM scores"))
        ).scalar_one()
        after_events = (
            await conn.execute(text("SELECT count(*) FROM events"))
        ).scalar_one()
        db_size = (
            await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
        ).scalar_one()

    log.info(
        "after:  signals=%s, scores=%s, events=%s, db_total=%s",
        f"{after_signals:,}",
        f"{after_scores:,}",
        f"{after_events:,}",
        db_size,
    )
    log.info(
        "freed: signals %s rows, scores %s rows",
        f"{before_signals - after_signals:,}",
        f"{before_scores - after_scores:,}",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Emergency DB collapse-to-latest.")
    p.add_argument(
        "--commit",
        action="store_true",
        help="Actually run TRUNCATE + dedupe + VACUUM. Default is dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
