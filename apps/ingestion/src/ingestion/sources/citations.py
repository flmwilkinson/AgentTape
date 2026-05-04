"""arXiv citation counts.

Replaces the old Semantic Scholar ingestor. OpenAlex is the open-data
replacement that doesn't gate personal-email signups — set
``OPENALEX_MAILTO`` (any address you read; goes in the "polite pool")
and you get 100k requests/day for free.

Falls back to Semantic Scholar if ``SEMANTIC_SCHOLAR_API_KEY`` is set
and ``OPENALEX_MAILTO`` is not, so existing deployments keep working.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org/works"
S2_BASE = "https://api.semanticscholar.org/graph/v1/paper/arXiv:"


class ArxivCitationsIngestor(Ingestor):
    """For agents with arxiv_ids, sum citation counts across listed papers."""

    name: ClassVar[str] = "arxiv_citations"
    source: ClassVar[SignalSource] = SignalSource.ARXIV_CITATIONS
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # Pick the provider once per pass. OpenAlex is preferred — open
        # data, no email gating, generous rate. We only fall back to
        # Semantic Scholar if its key is set and OpenAlex's mailto is
        # not, which preserves any existing deployment that wired S2
        # before OpenAlex landed.
        provider = self._provider()
        if provider is None:
            return []

        sem = asyncio.Semaphore(3)

        async def one(a: AgentRow) -> SignalReading | None:
            ids = a.arxiv_ids or []
            if not ids:
                return None
            total = 0
            any_hit = False
            for arxiv_id in ids:
                async with sem:
                    count = await provider(arxiv_id)
                if count is None:
                    continue
                total += count
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

    def _provider(self):
        """Return an awaitable (arxiv_id) -> int|None, or None to skip."""
        if self.settings.openalex_mailto:
            mailto = self.settings.openalex_mailto

            async def via_openalex(arxiv_id: str) -> int | None:
                # OpenAlex resolves arXiv IDs natively via the
                # arXiv source URL form; safer than parsing.
                url = f"{OPENALEX_BASE}/https://arxiv.org/abs/{arxiv_id}"
                try:
                    r = await self._http.get(url, params={"mailto": mailto})
                except Exception:  # noqa: BLE001
                    return None
                if r.status_code != 200:
                    return None
                try:
                    return int((r.json() or {}).get("cited_by_count") or 0)
                except (ValueError, TypeError):
                    return None

            return via_openalex

        if self.settings.semantic_scholar_api_key:
            headers = {"x-api-key": self.settings.semantic_scholar_api_key}

            async def via_s2(arxiv_id: str) -> int | None:
                try:
                    r = await self._http.get(
                        f"{S2_BASE}{arxiv_id}",
                        params={"fields": "citationCount"},
                        headers=headers,
                    )
                except Exception:  # noqa: BLE001
                    return None
                if r.status_code != 200:
                    return None
                try:
                    return int((r.json() or {}).get("citationCount") or 0)
                except (ValueError, TypeError):
                    return None

            return via_s2

        # Neither configured — soft-skip the whole source rather than
        # spamming anonymous quotas (OpenAlex without mailto is allowed
        # but rate-limited harder).
        return None
