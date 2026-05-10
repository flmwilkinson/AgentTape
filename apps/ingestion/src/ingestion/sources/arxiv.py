"""arXiv mention count — number of papers that mention the agent.

We use the public arXiv search endpoint (Atom). Slow tier: refresh
mention counts daily for the whole admitted set.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

import feedparser

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.name_tokens import search_tokens

log = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"


class ArxivIngestor(Ingestor):
    """``arxiv_citations`` is reused here as the carrier for paper-mention count.

    The schema only has one arxiv-shaped signal source (``arxiv_citations``)
    and Semantic Scholar gives us the citation count for a *specific paper*.
    We use this ingestor to count mentions of the *agent name* across new
    arXiv papers — a softer adoption signal.
    """

    name: ClassVar[str] = "arxiv_mentions"
    source: ClassVar[SignalSource] = SignalSource.ARXIV_CITATIONS
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(2)

        async def one(a: AgentRow) -> SignalReading | None:
            # Build a single OR-of-quoted-tokens search rather than
            # multiple round-trips. For FMs that means the openrouter
            # id, the clean name ("GPT-5"), the no-provider slug, and
            # the full slug all participate. arXiv's search syntax
            # supports OR across quoted phrases via "all:"X" OR "Y"".
            tokens = search_tokens(a)
            if not tokens:
                return None
            # Cap at 4 to keep the URL short — arxiv's tolerant of
            # complex queries but no need to exceed it.
            ored = " OR ".join(f'"{t}"' for t in tokens[:4])
            async with sem:
                try:
                    r = await self._http.get(
                        ARXIV_API,
                        params={
                            "search_query": f"all:({ored})",
                            "max_results": 100,
                        },
                    )
                except Exception:  # noqa: BLE001
                    return None
            if r.status_code != 200:
                return None
            feed = feedparser.parse(r.text)
            count = len(feed.entries)
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.ARXIV_CITATIONS,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]
