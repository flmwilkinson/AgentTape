"""One-shot backfill of capability/deployment/license/maturity tags
across already-admitted application agents.

Why this exists: the rules-based enrichment shipped after the first
batch of agents were admitted, so they have no tags. Without tags,
sector indexes (CODE-25, WEB-25, OSS-50, MCP-25) can't find any
constituents.

Re-runs are safe — every tag insert is ON CONFLICT DO NOTHING.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.backfill_tags
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings
from discovery.enrichment import _tags_from_rules
from discovery.promoter import _attach_tag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_tags")


async def main() -> None:
    settings = get_settings()
    # The container's DATABASE_URL is plain postgres:// for the API; the
    # script needs the asyncpg driver explicitly.
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Pull every admitted application agent and join the original
        # discovery_candidates payload so we have the GitHub topics /
        # license / homepage etc. that the rules engine looks at.
        rows = (
            await session.execute(
                text(
                    """
                    SELECT a.id, a.slug, a.name, a.description, a.github_repo,
                        dc.raw_payload
                    FROM agents a
                    LEFT JOIN discovery_candidates dc
                        ON dc.promoted_to_agent_id = a.id
                    WHERE a.eligibility_status = 'admitted'
                      AND a.entity_kind = 'application'
                    """
                )
            )
        ).all()

        log.info("backfilling tags for %d application agents", len(rows))
        tagged = 0
        for agent_id, slug, name, description, github_repo, raw_payload in rows:
            payload: dict[str, Any] = dict(raw_payload or {})
            # Layer the agent's own facts on top — these are what the
            # post-admission record has, in case raw_payload is sparse.
            payload.setdefault("name", name)
            payload.setdefault("description", description or "")
            if github_repo and not payload.get("full_name"):
                payload["full_name"] = github_repo

            tags = _tags_from_rules(payload)
            any_written = False
            for kind, values in tags.items():
                for value in values:
                    await _attach_tag(session, agent_id, kind, value)
                    any_written = True
            if any_written:
                tagged += 1
                log.info("tagged %s -> %s", slug, _summarize_tags(tags))

        await session.commit()
        log.info("backfill complete: tagged=%d / total=%d", tagged, len(rows))

    await engine.dispose()


def _summarize_tags(tags: dict[str, list[str]]) -> str:
    return ", ".join(
        f"{k}={v[0]}" if len(v) == 1 else f"{k}={v}"
        for k, v in tags.items()
        if v
    )


if __name__ == "__main__":
    asyncio.run(main())
