"""FastAPI app for the ingestion service container.

The container runs ``uvicorn ingestion.main:app``; the lifespan hook
starts the three-tier scheduler in-process. Set
``INGESTION_SCHEDULER=off`` to launch /health-only (useful for quickly
iterating on the API without the schedulers eating CPU).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from ingestion.config import get_settings
from ingestion.scheduler import build_schedulers

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    schedulers: dict[str, Any] = {}
    if os.environ.get("INGESTION_SCHEDULER", "on").lower() != "off":
        schedulers = build_schedulers(get_settings())
        for sched in schedulers.values():
            sched.start()
        log.info("ingestion schedulers started: %s", list(schedulers))
    yield
    for sched in schedulers.values():
        sched.shutdown(wait=False)


app = FastAPI(title="AgentTape Ingestion", version="0.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
