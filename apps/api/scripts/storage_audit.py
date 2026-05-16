"""Storage audit — print where the database bytes actually are.

Read-only. Reports:

  • Total database size.
  • Per-table size (table + indexes + TOAST), descending.
  • Row counts per table.
  • Oldest row per time-series table — tells us how much history is
    sitting around vs. what we'd actually keep under a retention rule.

Run inside the API container so we use the same DATABASE_URL the
app uses:

    docker compose -f infra/cloud/docker-compose.cloud.yml exec api \\
        python -m scripts.storage_audit

If you're running locally:

    cd apps/api && uv run python -m scripts.storage_audit
"""
from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("storage_audit")


# Time-series tables — for each, we also report the oldest row so a
# reader can see "we have 14 months of signals" or "events go back to
# Jan" at a glance. Add to this list if new append-only tables show up.
TIME_SERIES_TABLES: list[tuple[str, str]] = [
    ("signals", "captured_at"),
    ("scores", "computed_at"),
    ("events", "created_at"),
    ("index_snapshots", "captured_at"),
    ("rebalance_logs", "run_at"),
    ("benchmark_results", "captured_at"),
    ("discovery_candidates", "found_at"),
]


async def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    # asyncpg doesn't accept libpq-only query params; strip them.
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts = urlsplit(url)
    drop = {"sslmode", "channel_binding"}
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in drop]
    url = urlunsplit(parts._replace(query=urlencode(qs)))

    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # 1. Database total.
        row = (
            await session.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
        ).scalar_one()
        print()
        print("=== Database total ===")
        print(f"  {row}")

        # 2. Per-table sizes — total relation size includes table heap +
        # all indexes + TOAST. Sorted descending so the worst offenders
        # are at the top of the output.
        rows = await session.execute(
            text(
                """
                SELECT
                    c.relname AS table_name,
                    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                    pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
                    pg_size_pretty(
                        pg_total_relation_size(c.oid) - pg_relation_size(c.oid)
                    ) AS index_toast_size,
                    pg_total_relation_size(c.oid) AS bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                ORDER BY pg_total_relation_size(c.oid) DESC
                """
            )
        )
        print()
        print("=== Tables, biggest first ===")
        print(
            f"  {'table':<30}  {'total':>10}  {'table':>10}  {'idx+toast':>10}"
        )
        print("  " + "-" * 66)
        for r in rows:
            print(
                f"  {r.table_name:<30}  {r.total_size:>10}  "
                f"{r.table_size:>10}  {r.index_toast_size:>10}"
            )

        # 3. Row counts. Done separately because pg_class.reltuples is
        # a stale estimate; for an audit we want exact numbers and
        # SELECT count(*) is fine on these tables.
        print()
        print("=== Row counts ===")
        table_names_rows = await session.execute(
            text(
                """
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY c.relname
                """
            )
        )
        for r in table_names_rows:
            try:
                count = (
                    await session.execute(
                        text(f'SELECT count(*) FROM "{r.relname}"')
                    )
                ).scalar_one()
                print(f"  {r.relname:<30}  {count:>12,}")
            except Exception as e:  # noqa: BLE001
                print(f"  {r.relname:<30}  (count failed: {e})")

        # 4. Oldest row in each time-series table — direct evidence of
        # how much history we'd reclaim under a retention policy.
        print()
        print("=== Time-series history ===")
        for tbl, col in TIME_SERIES_TABLES:
            try:
                row = (
                    await session.execute(
                        text(
                            f"SELECT min({col}) AS oldest, max({col}) AS newest, "
                            f"count(*) AS n FROM {tbl}"
                        )
                    )
                ).first()
                if row and row.n:
                    span = row.newest - row.oldest if row.newest else None
                    print(
                        f"  {tbl:<22}  n={row.n:>10,}  "
                        f"oldest={row.oldest}  span={span}"
                    )
                else:
                    print(f"  {tbl:<22}  (empty)")
            except Exception as e:  # noqa: BLE001
                print(f"  {tbl:<22}  (audit failed: {e})")

        # 5. Per-source signal row counts — within signals, which sources
        # are dominating? Helpful for choosing per-source retention if
        # the global 90-day rule isn't enough.
        print()
        print("=== Signal rows by source (top 15) ===")
        try:
            rows = await session.execute(
                text(
                    """
                    SELECT source::text AS source, count(*) AS n,
                           min(captured_at) AS oldest
                    FROM signals
                    GROUP BY source
                    ORDER BY count(*) DESC
                    LIMIT 15
                    """
                )
            )
            for r in rows:
                print(f"  {r.source:<32}  n={r.n:>10,}  oldest={r.oldest}")
        except Exception as e:  # noqa: BLE001
            print(f"  (signals breakdown failed: {e})")

        print()


if __name__ == "__main__":
    asyncio.run(main())
