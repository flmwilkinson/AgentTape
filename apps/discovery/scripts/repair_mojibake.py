"""One-shot repair of mojibake in stored agent descriptions.

Why this exists: some descriptions arrived with UTF-8 multi-byte
sequences ASCII-replaced upstream (each byte → "?"), so a smart
apostrophe became "???". The discovery sanitizer in
enrichment._clean_text() now catches these patterns at ingest, but
existing rows already in the database are still mangled — this
script applies the same substitutions in-place.

Re-runs are safe: every fix is an idempotent string replace.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.repair_mojibake
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings
from discovery.enrichment import _MOJIBAKE_FIXES, _clean_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("repair_mojibake")


async def main() -> None:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Build an OR pattern that matches any of the mojibake markers, so
    # the SELECT only pulls rows we'd actually rewrite. LIKE patterns
    # are fine here — the marker strings contain no LIKE wildcards.
    or_clauses = " OR ".join(
        ["description LIKE :p" + str(i) for i, _ in enumerate(_MOJIBAKE_FIXES)]
    )
    select_params = {
        f"p{i}": f"%{bad}%" for i, (bad, _) in enumerate(_MOJIBAKE_FIXES)
    }

    async with Session() as session:
        rows = await session.execute(
            text(f"SELECT id, description FROM agents WHERE {or_clauses}"),
            select_params,
        )
        targets = list(rows)
        log.info("matched %d agent rows with mojibake markers", len(targets))

        fixed = 0
        for r in targets:
            cleaned = _clean_text(r.description or "")
            if cleaned == r.description:
                continue
            await session.execute(
                text("UPDATE agents SET description = :d WHERE id = :id"),
                {"d": cleaned, "id": r.id},
            )
            fixed += 1
        await session.commit()
        log.info("rewrote %d / %d", fixed, len(targets))


if __name__ == "__main__":
    asyncio.run(main())
