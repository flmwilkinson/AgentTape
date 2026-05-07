"""github_issue_close_rate_30d — maintainer responsiveness as a quality signal.

Closed issues last 30d divided by opened issues last 30d. ≥1.0 means the
project is keeping up; <0.5 means it's drifting into bug-tracker
abandonment regardless of star count. We multiply by 100 so the value
sits naturally on the same 0–100ish scale as other quality signals,
clamped to 200 (sustained 2× close-rate is "very responsive" but not
infinitely better).

GitHub's search API returns total counts for queries like
``repo:{owner}/{repo} is:issue created:>={since}`` so we don't have to
walk every issue.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

SEARCH = "https://api.github.com/search/issues"


class GithubIssueCloseRate30dIngestor(Ingestor):
    name: ClassVar[str] = "github_issue_close_rate_30d"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_ISSUE_CLOSE_RATE_30D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.github_token
        if not token:
            # Search API rate limit is 30 req/min authenticated, 10
            # unauthenticated. With two queries per agent we'd burn
            # the anonymous quota in a tier — skip.
            return []
        # Search API is the one that throttles fastest, so serialize.
        sem = asyncio.Semaphore(2)
        since = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": self.settings.user_agent,
        }

        async def one(a: AgentRow) -> SignalReading | None:
            if not a.github_repo or "/" not in a.github_repo:
                return None
            async with sem:
                opened = await _count(
                    self._http,
                    headers,
                    f"repo:{a.github_repo} is:issue created:>={since}",
                )
                if opened is None:
                    return None
                closed = await _count(
                    self._http,
                    headers,
                    f"repo:{a.github_repo} is:issue closed:>={since}",
                )
            if closed is None:
                return None
            if opened == 0:
                # No new issues in 30d. Treat as a healthy baseline
                # rather than a divide-by-zero — score 100 (i.e. 1.0
                # close-rate) so quiet repos don't get punished.
                ratio = 1.0
            else:
                ratio = closed / opened
            value = max(0.0, min(2.0, ratio)) * 100.0
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.GITHUB_ISSUE_CLOSE_RATE_30D,
                value=value,
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _count(http, headers: dict[str, str], q: str) -> int | None:
    """Total_count for a /search/issues query, or None on transient error."""
    try:
        r = await http.get(
            SEARCH, headers=headers, params={"q": q, "per_page": 1}
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code == 422:
        # Malformed search; treat as no signal rather than crash.
        return None
    if r.status_code != 200:
        return None
    try:
        return int((r.json() or {}).get("total_count") or 0)
    except (ValueError, TypeError):
        return None
