"""Apply the model_dep tag seed list.

Reads ``seed_model_deps.json`` (next to this script) and, for every
agent slug listed there, inserts a tag of kind=model_dep pointing at
each foundation-model slug. Both the agent and the FM must already
exist in the database — entries that don't resolve are skipped with
a log line so you can see which ones to adjust in the seed file.

Idempotent: tag rows are upsert-on-conflict, agent_tags links are
ON CONFLICT DO NOTHING. Safe to re-run after you edit the seed.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.seed_model_deps
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
log = logging.getLogger("seed_model_deps")

SEED_PATH = Path(__file__).parent / "seed_model_deps.json"


async def main() -> None:
    seed = json.loads(SEED_PATH.read_text())
    # Drop the README key so iterating gives us only the real entries.
    seed.pop("_README", None)

    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    inserted = 0
    skipped_agents = 0
    skipped_models = 0

    async with Session() as session:
        for agent_slug, model_slugs in seed.items():
            agent_row = (
                await session.execute(
                    text("SELECT id FROM agents WHERE slug = :s"),
                    {"s": agent_slug},
                )
            ).first()
            if not agent_row:
                log.warning("agent slug not in db: %s — skipping", agent_slug)
                skipped_agents += 1
                continue

            for model_slug in model_slugs:
                model_row = (
                    await session.execute(
                        text(
                            "SELECT id, name FROM agents "
                            "WHERE slug = :s AND entity_kind = 'foundation_model'"
                        ),
                        {"s": model_slug},
                    )
                ).first()
                if not model_row:
                    log.warning(
                        "model slug not in db: %s — skipping (agent %s)",
                        model_slug,
                        agent_slug,
                    )
                    skipped_models += 1
                    continue

                # Tag rows live in ``tags`` keyed by (kind, value).
                # Insert-or-fetch the tag id, then link via agent_tags.
                tag_row = (
                    await session.execute(
                        text(
                            """
                            INSERT INTO tags (id, kind, value, display_name)
                            VALUES (gen_random_uuid(),
                                    CAST(:kind AS tag_kind),
                                    :value, :display_name)
                            ON CONFLICT (kind, value)
                            DO UPDATE SET display_name = EXCLUDED.display_name
                            RETURNING id
                            """
                        ),
                        {
                            "kind": "model_dep",
                            "value": model_slug,
                            "display_name": model_row.name,
                        },
                    )
                ).first()

                await session.execute(
                    text(
                        """
                        INSERT INTO agent_tags (agent_id, tag_id)
                        VALUES (:aid, :tid)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"aid": agent_row.id, "tid": tag_row.id},
                )
                inserted += 1

        await session.commit()

    log.info(
        "model_dep seed: linked %d, skipped %d unknown agents, %d unknown models",
        inserted,
        skipped_agents,
        skipped_models,
    )


if __name__ == "__main__":
    asyncio.run(main())
