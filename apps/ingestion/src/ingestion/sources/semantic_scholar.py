"""Semantic Scholar citation counts for an agent's arXiv paper(s)."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

S2_API = "https://api.semanticscholar.org/graph/v1/paper/arXiv:"


class ArxivCitationsIngestor(Ingestor):
    """For agents with arxiv_ids, sum citation counts across listed papers."""

    name: ClassVar[str] = "arxiv_citations"
    source: ClassVar[SignalSource] = SignalSource.ARXIV_CITATIONS
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(3)
        headers: dict[str, str] = {}
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key

        async def one(a: AgentRow) -> SignalReading | None:
            ids = a.arxiv_ids or []
            if not ids:
                return None
            total = 0
            any_hit = False
            for arxiv_id in ids:
                async with sem:
                    try:
                        r = await self._http.get(
                            f"{S2_API}{arxiv_id}",
                            params={"fields": "citationCount"},
                            headers=headers,
                        )
                    except Exception:  # noqa: BLE001
                        continue
                if r.status_code != 200:
                    continue
                total += int((r.json() or {}).get("citationCount") or 0)
                any_hit = True
            if not any_hit:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.ARXIV_CITATIONS,
                value=float(total),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]
