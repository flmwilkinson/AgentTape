"""Walk every admitted application with a github_repo and try to
auto-detect its npm / PyPI package name from the repo's package.json
or pyproject.toml. Fills in ``agents.package_names`` for the missing
ecosystems without overwriting anything that's already there.

The promoter does this at admit time for new candidates; this script
covers everything that was admitted before the auto-detector landed.

Idempotent: safe to re-run after the seed file is edited or after a
batch of new repos appears.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.backfill_github_packages
"""
from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings
from discovery.enrichment import detect_packages_from_github

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_github_packages")


async def main() -> None:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    walked = 0
    updated = 0

    async with Session() as session:
        # Only application rows — foundation models don't have GitHub
        # repos in the same sense (the "github_repo" on an FM row is
        # rarely a packaging target). entity_kind filter keeps the
        # backfill scoped and fast.
        rows = await session.execute(
            text(
                """
                SELECT id, slug, github_repo, package_names
                FROM agents
                WHERE eligibility_status = 'admitted'
                  AND entity_kind = 'application'
                  AND github_repo IS NOT NULL
                """
            )
        )
        targets = list(rows)
        log.info("walking %d admitted apps with a github_repo", len(targets))

        for r in targets:
            walked += 1
            current = r.package_names or {}
            try:
                detected = await detect_packages_from_github(r.github_repo)
            except Exception as e:  # noqa: BLE001
                log.debug("detect failed for %s (%s): %s", r.slug, r.github_repo, e)
                continue
            if not detected:
                continue
            # Only fill in keys we don't already have. Manual seed and
            # source-payload values always win.
            merged = dict(current)
            changed = False
            for k, v in detected.items():
                if not current.get(k):
                    merged[k] = v
                    changed = True
            if not changed:
                continue
            await session.execute(
                text(
                    "UPDATE agents SET package_names = CAST(:p AS jsonb) "
                    "WHERE id = :id"
                ),
                {"p": json.dumps(merged), "id": r.id},
            )
            updated += 1

        await session.commit()

    log.info(
        "backfill_github_packages: walked %d, filled in %d", walked, updated
    )


if __name__ == "__main__":
    asyncio.run(main())
