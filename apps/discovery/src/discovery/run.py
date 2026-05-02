"""CLI: ``python -m discovery.run [scout_name|promoter|all]``.

Examples:

    python -m discovery.run github_search
    python -m discovery.run promoter
    python -m discovery.run all

``all`` runs every scout in parallel, then runs the promoter once.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from discovery.config import get_settings
from discovery.db import session_factory
from discovery.promoter import run_promoter
from discovery.scouts import ALL_SCOUTS, SCOUT_BY_NAME, Scout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
)
log = logging.getLogger("discovery.run")


async def _run_scout(scout_cls: type[Scout]) -> dict[str, Any]:
    settings = get_settings()
    scout = scout_cls(settings)
    try:
        async with session_factory()() as session:
            inserted = await scout.run(session)
        return {"scout": scout_cls.name, "inserted": inserted}
    finally:
        await scout.aclose()


async def _run_promoter() -> dict[str, Any]:
    async with session_factory()() as session:
        return {"promoter": await run_promoter(session)}


async def _run_all() -> dict[str, Any]:
    scout_results = await asyncio.gather(
        *(_run_scout(cls) for cls in ALL_SCOUTS), return_exceptions=True
    )
    cleaned: list[Any] = []
    for cls, r in zip(ALL_SCOUTS, scout_results, strict=True):
        if isinstance(r, BaseException):
            log.error("scout %s failed: %s", cls.name, r)
            cleaned.append({"scout": cls.name, "error": str(r)})
        else:
            cleaned.append(r)
    promoter_result = await _run_promoter()
    return {"scouts": cleaned, **promoter_result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discovery.run")
    targets = sorted(SCOUT_BY_NAME) + ["promoter", "all"]
    parser.add_argument(
        "target",
        choices=targets,
        help="scout name, 'promoter', or 'all' (every scout then the promoter)",
    )
    args = parser.parse_args(argv)

    if args.target == "all":
        result = asyncio.run(_run_all())
    elif args.target == "promoter":
        result = asyncio.run(_run_promoter())
    else:
        result = asyncio.run(_run_scout(SCOUT_BY_NAME[args.target]))

    import json as _json

    print(_json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
