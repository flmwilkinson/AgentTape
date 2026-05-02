"""Hacker News mention count over the last 7 days.

One Algolia call per agent isn't free but the count is small (one batch
per fast tier tick) and the API is generous. We search by the agent's
slug AND by its github_repo full name to catch both naming styles.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

ALGOLIA = "https://hn.algolia.com/api/v1/search"


class HNMentions7dIngestor(Ingestor):
    name: ClassVar[str] = "hn_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.HN_MENTIONS_7D
    tier: ClassVar[str] = "fast"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        since = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
        # Throttle to be polite — Algolia rate-limits aggressive callers.
        sem = asyncio.Semaphore(4)

        async def one(a: AgentRow) -> SignalReading | None:
            term = a.github_repo or a.slug
            if not term:
                return None
            async with sem:
                try:
                    r = await self._http.get(
                        ALGOLIA,
                        params={
                            "query": term,
                            "tags": "(story,comment)",
                            "numericFilters": f"created_at_i>{since}",
                            "hitsPerPage": 0,
                        },
                    )
                except Exception:  # noqa: BLE001
                    return None
            if r.status_code != 200:
                return None
            count = (r.json() or {}).get("nbHits")
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.HN_MENTIONS_7D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]
