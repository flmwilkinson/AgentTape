"""Delete already-admitted OpenRouter routing aliases.

The scout (discovery.scouts.openrouter_models) now skips
``:nitro``/``:fast``/``:online``/``:beta``/``:extended`` suffixes at
admission, but rows admitted before that filter landed are still in
``agents``. This script finds them by their stored openrouter_id
fact and removes the row + cascading children (signals, agent_tags,
benchmark_results).

Match logic: read each agent's most-recent ``discovery_candidates``
``raw_payload`` for an ``openrouter_id`` and check if it ends in any
of the routing-alias suffixes. Doing it from the payload rather
than the slug keeps us robust if slug-generation rules change.

Idempotent: re-running after the deletes is a no-op.

Run inside the discovery container:
    docker compose exec discovery python -m scripts.purge_routing_aliases
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from discovery.config import get_settings
from discovery.scouts.openrouter_models import _ROUTING_ALIASES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("purge_routing_aliases")


async def main() -> None:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    engine = create_async_engine(url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # JSONB ->> 'openrouter_id' returns text; string match against
        # each routing suffix. Using a CTE keeps the SELECT and DELETE
        # consistent in one transaction.
        like_clauses = " OR ".join(
            ["dc.raw_payload ->> 'openrouter_id' LIKE :p" + str(i)
             for i in range(len(_ROUTING_ALIASES))]
        )
        params = {f"p{i}": f"%{s}" for i, s in enumerate(_ROUTING_ALIASES)}

        rows = await session.execute(
            text(
                f"""
                SELECT a.id, a.slug,
                       dc.raw_payload ->> 'openrouter_id' AS openrouter_id
                FROM agents a
                JOIN discovery_candidates dc ON dc.promoted_to_agent_id = a.id
                WHERE a.entity_kind = 'foundation_model'
                  AND ({like_clauses})
                """
            ),
            params,
        )
        targets = list(rows)
        log.info("found %d routing-alias rows to remove", len(targets))
        for r in targets:
            log.info("  removing %s (openrouter_id=%s)", r.slug, r.openrouter_id)
            # FK cascades on signals/agent_tags/benchmark_results clean
            # up the children. discovery_candidates.promoted_to_agent_id
            # is set null by ON DELETE so the candidate stays for audit.
            await session.execute(
                text("DELETE FROM agents WHERE id = :id"),
                {"id": r.id},
            )
        await session.commit()
        log.info("purge_routing_aliases: removed %d", len(targets))


if __name__ == "__main__":
    asyncio.run(main())
