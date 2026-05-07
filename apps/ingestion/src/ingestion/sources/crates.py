"""Crates.io recent download counts — Rust adoption signal.

Lots of MCP servers are built on Rust because the SDK landed there
first. Without a Crates.io ingestor we'd undercount Rust agents the
way an early-only-Python pipeline would. Free JSON, no auth:

    GET https://crates.io/api/v1/crates/{name}
    -> crate.recent_downloads (last 90 days)

Match key: ``agent.package_names["cargo"]`` set to the crate name.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = "https://crates.io/api/v1/crates/{name}"


class CratesDownloads90dIngestor(Ingestor):
    name: ClassVar[str] = "crates_downloads_90d"
    source: ClassVar[SignalSource] = SignalSource.CRATES_DOWNLOADS_90D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(8)
        # Crates.io asks for a descriptive User-Agent on their API
        # (see https://crates.io/policies). The shared httpx client
        # already sends self.settings.user_agent so we're fine.

        async def one(a: AgentRow) -> SignalReading | None:
            name = (a.package_names or {}).get("cargo")
            if not name:
                return None
            async with sem:
                downloads = await _recent_downloads(self._http, name)
            if downloads is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.CRATES_DOWNLOADS_90D,
                value=float(downloads),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _recent_downloads(http, name: str) -> int | None:
    """90-day download count for the named crate, or None."""
    try:
        r = await http.get(API.format(name=name))
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json() or {}
    except ValueError:
        return None
    crate = data.get("crate") or {}
    val = crate.get("recent_downloads")
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
