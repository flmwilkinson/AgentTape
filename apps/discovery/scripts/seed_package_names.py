"""Apply the package_names seed list to existing agent rows.

Why this exists: high-profile apps (claude-code, cursor, aider) ship
through npm/PyPI under names that don't match their GitHub repo, so
the discovery scout can't auto-detect them. Without
``agents.package_names``, the npm_weekly and pypi_monthly ingestion
sources skip them, which means Adoption misses the biggest single
adoption signal those apps have. We seed manually here to close the
gap; auto-detection covers everything else.

Idempotent: existing entries in ``package_names`` are kept and merged
with the seed values rather than overwritten. Safe to re-run after
edits to ``seed_package_names.json``.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.seed_package_names
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_package_names")

SEED_PATH = Path(__file__).parent / "seed_package_names.json"


async def main() -> None:
    seed = json.loads(SEED_PATH.read_text())
    seed.pop("_README", None)

    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    updated = 0
    skipped = 0

    async with Session() as session:
        for slug, packages in seed.items():
            row = (
                await session.execute(
                    text(
                        "SELECT id, package_names FROM agents WHERE slug = :s"
                    ),
                    {"s": slug},
                )
            ).first()
            if not row:
                log.warning("agent slug not in db: %s — skipping", slug)
                skipped += 1
                continue

            current = row.package_names or {}
            # Merge — preserve existing keys, fill in missing ones.
            merged = {**current, **packages}
            if merged == current:
                # Nothing new to write; skip the UPDATE so the row's
                # updated_at trigger (if any) doesn't fire.
                continue

            await session.execute(
                text(
                    "UPDATE agents SET package_names = CAST(:p AS jsonb) "
                    "WHERE id = :id"
                ),
                {"p": json.dumps(merged), "id": row.id},
            )
            updated += 1

        await session.commit()

    log.info(
        "package_names seed: updated %d agents, skipped %d unknown slugs",
        updated,
        skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
