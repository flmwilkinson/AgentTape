"""Scout base class.

A scout is a single source-of-discovery: GitHub, HF, MCP, HN, arXiv, packages.
Each implementation produces ``Candidate`` rows; the base class handles the
boilerplate of writing them to ``discovery_candidates`` with idempotent
``ON CONFLICT (source, source_id) DO NOTHING`` semantics so re-running a
scout never produces duplicates.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.config import Settings
from discovery.enums import DiscoverySource

log = logging.getLogger(__name__)


@dataclass
class Candidate:
    """One unit of discovery — a thing that *might* become an agent."""

    source: DiscoverySource
    source_id: str  # repo full_name, HF model id, HN story id, arxiv id, ...
    raw_payload: dict[str, Any]


class Scout(ABC):
    name: ClassVar[str]
    interval_seconds: ClassVar[int]

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._http_owned = http is None
        self._http = http or httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        if self._http_owned:
            await self._http.aclose()

    @abstractmethod
    def discover(self) -> AsyncIterator[Candidate]:
        """Yield candidates from the source. Implementations are async generators."""

    async def run(self, session: AsyncSession) -> int:
        """Run one pass; insert new candidates; return count inserted."""
        inserted = 0
        seen = 0
        cap = self.settings.max_candidates_per_run
        async for cand in self.discover():
            seen += 1
            if seen > cap:
                log.info("scout %s hit cap of %d candidates", self.name, cap)
                break
            if await self._insert_candidate(session, cand):
                inserted += 1
        await session.commit()
        log.info(
            "scout %s saw %d, inserted %d new candidates",
            self.name,
            seen,
            inserted,
        )
        return inserted

    async def _insert_candidate(
        self, session: AsyncSession, cand: Candidate
    ) -> bool:
        """Insert a new candidate; return True iff a new row was added.

        On conflict, a promoted candidate whose raw_payload was nulled
        gets it back. That payload is the agent's facts store
        (openrouter_id etc.) and older retention runs stripped it, so
        re-seeing the candidate heals the agent. ``xmax = 0`` tells a
        fresh insert apart from that repair update.
        """
        result = await session.execute(
            text(
                """
                INSERT INTO discovery_candidates (id, source, source_id, raw_payload)
                VALUES (gen_random_uuid(), CAST(:source AS discovery_source), :sid, CAST(:payload AS jsonb))
                ON CONFLICT (source, source_id) DO UPDATE
                    SET raw_payload = EXCLUDED.raw_payload
                    WHERE discovery_candidates.raw_payload IS NULL
                      AND discovery_candidates.promoted_to_agent_id IS NOT NULL
                RETURNING (xmax = 0) AS inserted
                """
            ),
            {
                "source": cand.source.value,
                "sid": cand.source_id,
                "payload": _to_json(cand.raw_payload),
            },
        )
        row = result.first()
        return bool(row and row[0])


def _to_json(payload: dict[str, Any]) -> str:
    import json

    def default(o: Any) -> str:
        return str(o)

    return json.dumps(payload, default=default)
