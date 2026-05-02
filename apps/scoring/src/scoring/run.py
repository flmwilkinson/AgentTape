"""CLI: ``python -m scoring.run [target]``.

Targets:
    recompute   one-shot recompute every admitted agent
    rebalance   one-shot rebalance every index (or pass --index <slug>)
    snapshot    one-shot hourly-snapshot job
    subscriber  daemon: listen for ticks + run debounced recomputes
    all         daemon: subscriber + scheduler (snapshot/rebalance) — what
                ``uvicorn scoring.main:app`` runs in the container
    init        upsert the five launch indexes
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys

import redis.asyncio as redis_async

from scoring.compute import all_admitted_agent_ids, recompute_agents
from scoring.config import get_settings
from scoring.db import session_factory
from scoring.debouncer import get_debouncer
from scoring.indexes import (
    CATALOG_BY_SLUG,
    ensure_indexes,
    rebalance_all,
    rebalance_index,
    snapshot_all_indexes,
)
from scoring.scheduler import build_scheduler
from scoring.subscriber import run_subscriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
)
log = logging.getLogger("scoring.run")


async def _open_redis():
    return redis_async.from_url(get_settings().redis_url, decode_responses=True)


async def _cmd_recompute() -> dict:
    redis_client = await _open_redis()
    try:
        async with session_factory()() as session:
            await ensure_indexes(session)
            ids = await all_admitted_agent_ids(session)
        if not ids:
            return {"recomputed": 0, "reason": "no_admitted_agents"}
        async with session_factory()() as session:
            return await recompute_agents(session, ids, redis_client)
    finally:
        await redis_client.aclose()


async def _cmd_rebalance(slug: str | None) -> dict:
    redis_client = await _open_redis()
    try:
        async with session_factory()() as session:
            await ensure_indexes(session)
            if slug:
                return await rebalance_index(session, redis_client, slug)
            return await rebalance_all(session, redis_client)
    finally:
        await redis_client.aclose()


async def _cmd_snapshot() -> dict:
    async with session_factory()() as session:
        await ensure_indexes(session)
        return await snapshot_all_indexes(session)


async def _cmd_init() -> dict:
    async with session_factory()() as session:
        await ensure_indexes(session)
    return {"initialized": list(CATALOG_BY_SLUG)}


async def _cmd_subscriber() -> None:
    debouncer = get_debouncer()
    redis_client = await _open_redis()
    stop = asyncio.Event()

    def _stop() -> None:
        stop.set()
        debouncer.request_stop()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        pass  # windows asyncio

    sub_task = asyncio.create_task(run_subscriber(debouncer))
    deb_task = asyncio.create_task(debouncer.run(redis_client))

    await stop.wait()
    sub_task.cancel()
    deb_task.cancel()
    try:
        await sub_task
    except asyncio.CancelledError:
        pass
    try:
        await deb_task
    except asyncio.CancelledError:
        pass
    await redis_client.aclose()


async def _cmd_all() -> None:
    """Subscriber + scheduler + debouncer — what main.app runs in lifespan."""
    debouncer = get_debouncer()
    redis_client = await _open_redis()
    scheduler = build_scheduler()
    scheduler.start()

    stop = asyncio.Event()

    def _stop() -> None:
        stop.set()
        debouncer.request_stop()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        pass

    async with session_factory()() as session:
        await ensure_indexes(session)

    sub_task = asyncio.create_task(run_subscriber(debouncer))
    deb_task = asyncio.create_task(debouncer.run(redis_client))

    await stop.wait()
    scheduler.shutdown(wait=False)
    sub_task.cancel()
    deb_task.cancel()
    for t in (sub_task, deb_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await redis_client.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scoring.run")
    parser.add_argument(
        "target",
        choices=["recompute", "rebalance", "snapshot", "subscriber", "all", "init"],
    )
    parser.add_argument(
        "--index",
        help="for `rebalance`: only this index slug",
        choices=sorted(CATALOG_BY_SLUG),
        default=None,
    )
    args = parser.parse_args(argv)

    if args.target == "recompute":
        result = asyncio.run(_cmd_recompute())
    elif args.target == "rebalance":
        result = asyncio.run(_cmd_rebalance(args.index))
    elif args.target == "snapshot":
        result = asyncio.run(_cmd_snapshot())
    elif args.target == "init":
        result = asyncio.run(_cmd_init())
    elif args.target == "subscriber":
        asyncio.run(_cmd_subscriber())
        return 0
    elif args.target == "all":
        asyncio.run(_cmd_all())
        return 0
    else:
        parser.error(f"unknown target {args.target}")
        return 2

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
