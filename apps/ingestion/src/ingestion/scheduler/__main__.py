"""Daemon entry: ``python -m ingestion.scheduler``.

Builds three independent schedulers (fast / medium / slow), starts them,
and idles. SIGINT / SIGTERM stops them cleanly. The same code path is
used by the FastAPI ``main.app`` lifespan — this CLI is what
docker-compose runs directly.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from ingestion.config import get_settings
from ingestion.scheduler import build_schedulers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
)
log = logging.getLogger("ingestion.scheduler")


async def main() -> None:
    settings = get_settings()
    schedulers = build_schedulers(settings)

    for name, sched in schedulers.items():
        sched.start()
        log.info("started %s scheduler (interval handled by build_schedulers)", name)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _stop() -> None:
        log.info("stop requested; shutting down schedulers")
        stop.set()

    # Windows asyncio doesn't support add_signal_handler — fall back to KeyboardInterrupt.
    try:
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        pass

    try:
        await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for sched in schedulers.values():
            sched.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
