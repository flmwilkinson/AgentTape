"""Slow-tier one-shot runner.

Invoked by the host systemd timer in cloud deployments — runs every
slow-tier ingestor once, then exits cleanly. Replaces the in-process
APScheduler slow-tier interval which silently lost runs whenever the
host slept past the misfire-grace window (12 h on a 24 h interval).

Usage:
    python -m ingestion.run_slow_tier
"""
from __future__ import annotations

import asyncio
import logging
import sys

from ingestion.config import get_settings
from ingestion.scheduler import run_tier
from ingestion.tiers import SLOW, TierName
from ingestion.telemetry import init as init_telemetry

init_telemetry("agenttape-slow-tier")
log = logging.getLogger(__name__)


async def main() -> int:
    settings = get_settings()
    log.info("slow-tier one-shot starting; %d ingestors", len(SLOW))
    result = await run_tier(settings, TierName.SLOW, SLOW)
    log.info("slow-tier one-shot finished: %s", result)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
