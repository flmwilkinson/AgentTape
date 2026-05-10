"""Apply the model_dep tag seed list (family-level mappings).

Reads ``seed_model_deps.json`` and tags each listed agent with one or
more family-level model_dep values ('claude', 'gpt', etc). The
auto-detector (``detect_model_dep_families``) produces the same family
slugs from descriptions, so manual entries here and auto-detected ones
look the same on agent pages.

Idempotent: tag rows are upsert-on-conflict, agent_tags links are
ON CONFLICT DO NOTHING. Safe to re-run after editing the seed.

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

# Display names for family chips — keep matching the auto-detector's
# title-cased default. Add entries here when you add a new family to
# the detector pattern list in enrichment.py.
FAMILY_DISPLAY = {
    "claude": "Claude",
    "gpt": "GPT",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "llama": "Llama",
    "mistral": "Mistral",
    "qwen": "Qwen",
    "grok": "Grok",
}


async def main() -> None:
    seed = json.loads(SEED_PATH.read_text())
    seed.pop("_README", None)

    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    inserted = 0
    skipped_agents = 0
    unknown_families = 0

    async with Session() as session:
        for agent_slug, families in seed.items():
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

            for family in families:
                display = FAMILY_DISPLAY.get(family)
                if not display:
                    log.warning(
                        "unknown family '%s' for agent %s — skipping",
                        family,
                        agent_slug,
                    )
                    unknown_families += 1
                    continue

                tag_row = (
                    await session.execute(
                        text(
                            """
                            INSERT INTO tags (id, kind, value, display_name)
                            VALUES (gen_random_uuid(),
                                    CAST('model_dep' AS tag_kind),
                                    :value, :display_name)
                            ON CONFLICT (kind, value)
                            DO UPDATE SET display_name = EXCLUDED.display_name
                            RETURNING id
                            """
                        ),
                        {"value": family, "display_name": display},
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
        "model_dep seed: linked %d, skipped %d unknown agents, %d unknown families",
        inserted,
        skipped_agents,
        unknown_families,
    )


if __name__ == "__main__":
    asyncio.run(main())
