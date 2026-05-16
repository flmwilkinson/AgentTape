"""Remove zero-value signal rows from a tight time window.

Use case: after the emergency_cleanup brought the DB back, the
ingestion service kicked off its first scans and some sources
transiently returned 0 (rate-limited GitHub, half-warm Redis, etc).
Those zeros become the "latest reading" for their (agent, source)
pair and pollute scoring until the next tick replaces them.

This script DELETEs:

  * signals rows with value = 0 captured in the time window
  * (optionally) scores rows computed in the same window — they'll
    be recomputed correctly on the next scoring tick

Dry-run by default. Pass --commit to actually delete.

Usage:
    docker compose -f infra/cloud/docker-compose.cloud.yml exec api \\
        python -m scripts.remove_zero_readings \\
        --from "2026-05-16 11:30:00+00" \\
        --to   "2026-05-16 11:45:00+00" \\
        --commit

Add --include-scores to also delete score rows in the window.
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


async def main(args: argparse.Namespace) -> None:
    engine = create_async_engine(_engine_url(), echo=False)

    log.info(
        "window: %s → %s (commit=%s, include_scores=%s)",
        args.from_time,
        args.to_time,
        args.commit,
        args.include_scores,
    )

    # Preview counts so the dry-run gives a meaningful number.
    async with engine.connect() as conn:
        zero_signals = (
            await conn.execute(
                text(
                    """
                    SELECT count(*) FROM signals
                    WHERE value = 0
                      AND captured_at BETWEEN :a AND :b
                    """
                ),
                {"a": args.from_time, "b": args.to_time},
            )
        ).scalar_one()
        window_scores = (
            await conn.execute(
                text(
                    """
                    SELECT count(*) FROM scores
                    WHERE computed_at BETWEEN :a AND :b
                    """
                ),
                {"a": args.from_time, "b": args.to_time},
            )
        ).scalar_one()

    log.info(
        "would affect: signals(value=0)=%s rows; scores=%s rows",
        f"{zero_signals:,}",
        f"{window_scores:,}",
    )

    if not args.commit:
        log.info("dry-run — nothing changed. Re-run with --commit to delete.")
        return

    # Each DELETE in its own committed transaction so a failure on
    # scores doesn't roll back the signals delete.
    async with engine.begin() as conn:
        r = await conn.execute(
            text(
                """
                DELETE FROM signals
                WHERE value = 0
                  AND captured_at BETWEEN :a AND :b
                """
            ),
            {"a": args.from_time, "b": args.to_time},
        )
    log.info("signals: deleted %s rows", r.rowcount)

    if args.include_scores:
        async with engine.begin() as conn:
            r = await conn.execute(
                text(
                    """
                    DELETE FROM scores
                    WHERE computed_at BETWEEN :a AND :b
                    """
                ),
                {"a": args.from_time, "b": args.to_time},
            )
        log.info("scores: deleted %s rows", r.rowcount)
    else:
        log.info(
            "scores: not touched (pass --include-scores to delete in window)"
        )

    log.info("done. The next ingestion tick will repopulate fresh values.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Remove zero-value readings.")
    p.add_argument(
        "--from", dest="from_time",
        type=lambda s: datetime.fromisoformat(s),
        required=True,
        help="Start of time window, ISO format (e.g. '2026-05-16 11:30:00+00').",
    )
    p.add_argument(
        "--to", dest="to_time",
        type=lambda s: datetime.fromisoformat(s),
        required=True,
        help="End of time window, ISO format.",
    )
    p.add_argument(
        "--include-scores", action="store_true",
        help="Also delete scores rows in the same window (they recompute next tick).",
    )
    p.add_argument(
        "--commit", action="store_true",
        help="Actually delete. Default is dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
