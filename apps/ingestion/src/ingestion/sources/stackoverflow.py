"""Stack Overflow tag activity.

For agents whose name corresponds to a Stack Overflow tag (langchain,
crewai, autogen, llamaindex, etc.), count questions tagged in the
past week. Tag activity is a clean adoption signal — engineers asking
public questions about a tool means they're using it.

No auth needed for low rate. A free key from
https://stackapps.com/apps/oauth/register lifts the daily quota from
300 → 10,000 if you set ``STACKEXCHANGE_KEY``.

We only emit a signal for agents whose slug or GitHub repo name
matches a known tag — most agents won't, and that's fine.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = "https://api.stackexchange.com/2.3"


class StackOverflowQuestions7dIngestor(Ingestor):
    """Count of new questions tagged with the agent's name in the past 7 days."""

    name: ClassVar[str] = "stackoverflow_questions_7d"
    source: ClassVar[SignalSource] = SignalSource.STACKOVERFLOW_QUESTIONS_7D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        since = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
        sem = asyncio.Semaphore(2)
        common_params: dict[str, str | int] = {
            "site": "stackoverflow",
            "fromdate": since,
            "todate": int(time.time()),
            "filter": "total",  # response includes only the count
        }
        if self.settings.stackexchange_key:
            common_params["key"] = self.settings.stackexchange_key

        async def one(a: AgentRow) -> SignalReading | None:
            tag = _tag_for(a)
            if not tag:
                return None
            async with sem:
                count = await _count(self._http, tag, common_params)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.STACKOVERFLOW_QUESTIONS_7D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


def _tag_for(a: AgentRow) -> str | None:
    """Return a likely Stack Overflow tag for this agent, or None.

    SO tags are lowercase, dash-separated, single-word-ish. We try the
    GitHub repo's project portion first (more distinctive than slug)
    and accept if it looks like it could be a tag. The API returns 0
    cleanly for tags that don't exist, so being generous here is fine.
    """
    name = a.github_repo or a.slug or ""
    if "/" in name:
        name = name.split("/", 1)[1]
    name = name.lower().strip()
    if not name:
        return None
    # Skip obviously-not-a-tag: too short, contains spaces, all-numeric.
    if len(name) < 3 or " " in name or name.isdigit():
        return None
    return name


async def _count(http, tag: str, params: dict) -> int | None:
    try:
        r = await http.get(
            f"{API}/questions",
            params={**params, "tagged": tag},
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        return int((r.json() or {}).get("total") or 0)
    except (ValueError, TypeError):
        return None
