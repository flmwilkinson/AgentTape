"""Emergency cleanup — collapse the append-only tables to a sane
size when the regular retention rules can't help.

Critical implementation detail: each TRUNCATE runs in **its own
committed transaction**, separate from the SELECT that captures the
keep-set and separate from the INSERT that restores it. The reason
is Postgres MVCC: TRUNCATE inside a transaction does *not* free disk
space until that transaction commits. If TRUNCATE + INSERT live in
the same transaction (the obvious-looking shape), the INSERT hits
the same disk-full state because the truncated data is still on
disk waiting for commit. The earlier version of this script failed
exactly that way.

So the flow per table is:

  Phase 1 (read-only connection)
    SELECT the keep-set into Python memory. Tiny — at most ~17,500
    rows for signals (700 agents × 25 sources) and ~700 for scores.
  Phase 2 (own committed transaction)
    TRUNCATE the table. Commit. Postgres releases the heap pages
    immediately — no VACUUM needed.
  Phase 3 (own committed transaction)
    INSERT the keep-set back from memory.

After all tables are collapsed: VACUUM ANALYZE to update planner
stats. The TRUNCATEs already freed disk, so this is just statistics
maintenance — safe even when the DB was previously full.

DESTRUCTIVE. Loses signal/score history — current values are
preserved. Run with --commit explicitly to actually execute.

    docker compose -f infra/cloud/docker-compose.cloud.yml exec api \\
        python -m scripts.emergency_cleanup --commit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any
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


async def collapse_signals(engine) -> tuple[int, int]:
    """Returns (before_count, kept_count)."""
    async with engine.connect() as conn:
        before = (
            await conn.execute(text("SELECT count(*) FROM signals"))
        ).scalar_one()

    log.info(
        "signals: %s rows currently. Extracting latest-per-(agent,source)…",
        f"{before:,}",
    )

    # Phase 1: read keep-set into memory. Read-only connection. We
    # cast source to text so we can pass it back as a parameter to
    # the INSERT later (asyncpg needs the enum value as a string +
    # an explicit CAST).
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT DISTINCT ON (agent_id, source)
                    captured_at, agent_id, source::text AS source_text, value
                FROM signals
                ORDER BY agent_id, source, captured_at DESC
                """
            )
        )
        keep: list[dict[str, Any]] = [
            {
                "ts": r.captured_at,
                "aid": r.agent_id,
                "src": r.source_text,
                "val": float(r.value),
            }
            for r in rows
        ]
    log.info("  captured %s rows in memory", f"{len(keep):,}")

    # Phase 2: TRUNCATE in its own committed transaction. This is
    # the crucial part — the commit at the end of this block is
    # what tells Postgres it can release the old heap files.
    log.info("  TRUNCATE signals (separate transaction, frees pages)…")
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE signals"))
    log.info("  TRUNCATE committed. Disk space released.")

    # Phase 3: INSERT keep-set back. Separate transaction so the
    # commit happens cleanly. asyncpg supports executemany on the
    # raw connection but the SQLAlchemy AsyncConnection wraps that
    # awkwardly; we just loop. 4-17K inserts is well under a second.
    if keep:
        log.info("  INSERTing %s rows back…", f"{len(keep):,}")
        async with engine.begin() as conn:
            for row in keep:
                await conn.execute(
                    text(
                        """
                        INSERT INTO signals (id, captured_at, agent_id, source, value)
                        VALUES (gen_random_uuid(), :ts, :aid,
                                CAST(:src AS signal_source), :val)
                        """
                    ),
                    row,
                )
        log.info("  signals restored.")
    return before, len(keep)


async def collapse_scores(engine) -> tuple[int, int]:
    async with engine.connect() as conn:
        before = (
            await conn.execute(text("SELECT count(*) FROM scores"))
        ).scalar_one()

    log.info(
        "scores: %s rows currently. Extracting latest-per-agent…",
        f"{before:,}",
    )

    # Phase 1: read into memory.
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT DISTINCT ON (agent_id)
                    agent_id, computed_at,
                    agent_score, adoption, quality, momentum, community,
                    manipulation_resistance
                FROM scores
                ORDER BY agent_id, computed_at DESC
                """
            )
        )
        keep: list[dict[str, Any]] = [
            {
                "aid": r.agent_id,
                "ts": r.computed_at,
                "a": float(r.agent_score) if r.agent_score is not None else None,
                "ad": float(r.adoption) if r.adoption is not None else None,
                "q": float(r.quality) if r.quality is not None else None,
                "m": float(r.momentum) if r.momentum is not None else None,
                "c": float(r.community) if r.community is not None else None,
                "mr": (
                    float(r.manipulation_resistance)
                    if r.manipulation_resistance is not None
                    else None
                ),
            }
            for r in rows
        ]
    log.info("  captured %s rows in memory", f"{len(keep):,}")

    # Phase 2: TRUNCATE in own transaction.
    log.info("  TRUNCATE scores (separate transaction)…")
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE scores"))
    log.info("  TRUNCATE committed.")

    # Phase 3: restore.
    if keep:
        log.info("  INSERTing %s rows back…", f"{len(keep):,}")
        async with engine.begin() as conn:
            for row in keep:
                await conn.execute(
                    text(
                        """
                        INSERT INTO scores (
                            id, agent_id, computed_at,
                            agent_score, adoption, quality, momentum, community,
                            manipulation_resistance
                        )
                        VALUES (
                            gen_random_uuid(), :aid, :ts,
                            :a, :ad, :q, :m, :c, :mr
                        )
                        """
                    ),
                    row,
                )
        log.info("  scores restored.")
    return before, len(keep)


async def trim_events(engine) -> int:
    log.info("events: trimming to last 3 days…")
    async with engine.begin() as conn:
        r = await conn.execute(
            text(
                "DELETE FROM events WHERE created_at < now() - interval '3 days'"
            )
        )
    deleted = r.rowcount or 0
    log.info("  deleted %s rows", f"{deleted:,}")
    return deleted


async def vacuum(engine) -> None:
    log.info("VACUUM ANALYZE to refresh planner stats…")
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for tbl in ("signals", "scores", "events", "discovery_candidates"):
            try:
                await conn.execute(text(f"VACUUM ANALYZE {tbl}"))
                log.info("  VACUUM ANALYZE %s ok", tbl)
            except Exception as e:  # noqa: BLE001
                log.warning("  VACUUM %s failed: %s", tbl, e)


async def db_size(engine) -> str:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
        ).scalar_one()


async def main(args: argparse.Namespace) -> None:
    engine = create_async_engine(_engine_url(), echo=False)

    log.info("DB total before: %s", await db_size(engine))

    if not args.commit:
        # Dry-run just counts.
        async with engine.connect() as conn:
            for tbl in ("signals", "scores", "events"):
                n = (
                    await conn.execute(text(f"SELECT count(*) FROM {tbl}"))
                ).scalar_one()
                log.info("[dry-run] %s: %s rows", tbl, f"{n:,}")
        log.info("dry-run — nothing changed. Re-run with --commit.")
        return

    sig_before, sig_kept = await collapse_signals(engine)
    sco_before, sco_kept = await collapse_scores(engine)
    ev_deleted = await trim_events(engine)
    await vacuum(engine)

    log.info("=" * 60)
    log.info("DONE")
    log.info("  signals: %s → %s rows", f"{sig_before:,}", f"{sig_kept:,}")
    log.info("  scores:  %s → %s rows", f"{sco_before:,}", f"{sco_kept:,}")
    log.info("  events:  deleted %s rows", f"{ev_deleted:,}")
    log.info("  DB total after: %s", await db_size(engine))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Emergency DB collapse-to-latest.")
    p.add_argument(
        "--commit",
        action="store_true",
        help="Actually run TRUNCATE + restore + VACUUM. Default is dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
