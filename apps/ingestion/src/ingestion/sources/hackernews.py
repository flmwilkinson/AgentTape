"""Hacker News mention count over the last 7 days.

One Algolia call per agent isn't free but the count is small (one batch
per fast tier tick) and the API is generous. Applications search by
github_repo full name, falling back to slug; foundation models search
by their display name as an exact phrase (see ``fm_hn_phrase``).
"""
from __future__ import annotations

import asyncio
import logging
import re
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
            params: dict[str, str | int] = {
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{since}",
                "hitsPerPage": 0,
            }
            if a.entity_kind == "foundation_model":
                term = fm_hn_phrase(a.name)
                # Honour the quoted phrase.
                params["advancedSyntax"] = "true"
            else:
                term = a.github_repo or a.slug
            if not term:
                return None
            params["query"] = term
            async with sem:
                try:
                    r = await self._http.get(ALGOLIA, params=params)
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


def fm_hn_phrase(name: str | None) -> str | None:
    """Quoted phrase people actually write for a foundation model.

    FM slugs ("openai-gpt-5-2") almost never appear on HN, so the old
    slug query read 0 for most flagships, while a one-word name like
    "Pareto" matched every "Pareto frontier" comment and topped
    Adoption. Use the display name minus its "Provider: " prefix, as
    an exact phrase. A single plain word ("Pareto", "Sonar") is too
    generic to attribute, so return None and leave the signal unrated;
    joined brand names like "Qwen-Max" are distinctive and kept.
    """
    if not name:
        return None
    clean = re.sub(r"^[^:]+:\s*", "", name)
    clean = re.sub(r"[()]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return None
    if re.fullmatch(r"[A-Za-z]+", clean):
        return None
    return f'"{clean}"'
