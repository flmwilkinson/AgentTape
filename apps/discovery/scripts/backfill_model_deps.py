"""Scan every admitted application's description for model-dependency
phrases ("powered by Claude", "built on GPT-4", ...) and apply
model_dep:<family> tags accordingly.

The promoter does this at admit time for new candidates via
``detect_model_dep_families``; this script covers existing rows that
were admitted before the auto-detector landed.

Family slugs (claude / gpt / gemini / deepseek / llama / mistral /
qwen / grok) are the same set the detector emits. Manual seed entries
(``seed_model_deps.json``) can also create model_dep tags pointing at
specific FM slugs — those coexist fine with the family-level tags
this script writes.

Idempotent: ON CONFLICT DO NOTHING on tag inserts and agent_tags
links, so re-running adds new matches without touching existing rows.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.backfill_model_deps
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings
from discovery.enrichment import detect_model_dep_families

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_model_deps")


async def main() -> None:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    walked = 0
    tagged = 0

    async with Session() as session:
        rows = await session.execute(
            text(
                """
                SELECT id, slug, description
                FROM agents
                WHERE eligibility_status = 'admitted'
                  AND entity_kind = 'application'
                  AND description IS NOT NULL
                """
            )
        )
        targets = list(rows)
        log.info("walking %d admitted apps for model_dep phrases", len(targets))

        for r in targets:
            walked += 1
            families = detect_model_dep_families(r.description or "")
            if not families:
                continue
            for family in families:
                # Upsert tag row.
                await session.execute(
                    text(
                        """
                        INSERT INTO tags (id, kind, value, display_name)
                        VALUES (gen_random_uuid(),
                                CAST('model_dep' AS tag_kind),
                                :value, :display)
                        ON CONFLICT (kind, value) DO NOTHING
                        """
                    ),
                    {"value": family, "display": family.title()},
                )
                tag_id = (
                    await session.execute(
                        text(
                            "SELECT id FROM tags "
                            "WHERE kind = 'model_dep' AND value = :v"
                        ),
                        {"v": family},
                    )
                ).scalar_one()
                # Link agent → tag.
                await session.execute(
                    text(
                        """
                        INSERT INTO agent_tags (agent_id, tag_id)
                        VALUES (:aid, :tid)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"aid": r.id, "tid": tag_id},
                )
                tagged += 1

        await session.commit()

    log.info("backfill_model_deps: walked %d, tagged %d links", walked, tagged)


if __name__ == "__main__":
    asyncio.run(main())
