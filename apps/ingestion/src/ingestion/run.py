"""CLI for the ingestion service.

Two modes:

    python -m ingestion.run [tier|source]       — one-shot
    python -m ingestion.scheduler                — daemon mode

The daemon path is ``ingestion.scheduler.__main__`` (``python -m
ingestion.scheduler``); ``run.py`` is the one-shot path.

Examples:

    python -m ingestion.run fast
    python -m ingestion.run github_stars
    python -m ingestion.run all
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from ingestion.config import get_settings
from ingestion.db import session_factory
from ingestion.scheduler import run_tier
from ingestion.sources.base import load_admitted_agents, open_redis
from ingestion.tiers import INGESTOR_BY_NAME, TIERS, TierName

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
)
log = logging.getLogger("ingestion.run")


async def _run_one_source(name: str) -> dict:
    settings = get_settings()
    cls = INGESTOR_BY_NAME[name]
    redis_client = await open_redis(settings)
    try:
        async with session_factory()() as session:
            agents = await load_admitted_agents(session)
        ing = cls(settings)
        try:
            async with session_factory()() as session:
                stats = await ing.run(session, agents, redis_client)
            return {"ingestor": name, "agents": len(agents), **stats}
        finally:
            await ing.aclose()
    finally:
        await redis_client.aclose()


async def _run_one_tier(name: str) -> dict:
    settings = get_settings()
    return await run_tier(settings, name, TIERS[name])


async def _run_all_tiers() -> dict:
    settings = get_settings()
    out = []
    for tier_name, classes in TIERS.items():
        out.append(await run_tier(settings, tier_name, classes))
    return {"tiers": out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingestion.run")
    targets = (
        [TierName.FAST, TierName.MEDIUM, TierName.SLOW, "all"]
        + sorted(INGESTOR_BY_NAME)
    )
    parser.add_argument(
        "target",
        choices=targets,
        help="tier ('fast'|'medium'|'slow'), 'all', or a source name",
    )
    args = parser.parse_args(argv)

    if args.target == "all":
        result = asyncio.run(_run_all_tiers())
    elif args.target in TIERS:
        result = asyncio.run(_run_one_tier(args.target))
    else:
        result = asyncio.run(_run_one_source(args.target))

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
