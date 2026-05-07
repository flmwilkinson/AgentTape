"""github_releases_90d — release frequency over the last 90 days.

Stars accumulate forever; release cadence catches projects that look
big-on-paper but have stopped shipping. A repo with 10k stars but no
release in two years is a different proposition from the same repo
shipping every month, and that distinction is what this signal
exposes — feeds the Momentum pillar.

Token-gated: anonymous /releases is rate-limited to 60 req/h shared
across the IP, which would dent the medium tier. With a token we get
5,000 req/h.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = "https://api.github.com/repos/{owner}/{repo}/releases"


class GithubReleases90dIngestor(Ingestor):
    name: ClassVar[str] = "github_releases_90d"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_RELEASES_90D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.github_token
        if not token:
            return []
        sem = asyncio.Semaphore(8)
        cutoff = datetime.now(UTC) - timedelta(days=90)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": self.settings.user_agent,
        }

        async def one(a: AgentRow) -> SignalReading | None:
            if not a.github_repo or "/" not in a.github_repo:
                return None
            owner, repo = a.github_repo.split("/", 1)
            async with sem:
                count = await _release_count(self._http, headers, owner, repo, cutoff)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.GITHUB_RELEASES_90D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _release_count(
    http,
    headers: dict[str, str],
    owner: str,
    repo: str,
    cutoff: datetime,
) -> int | None:
    """Count releases created in [cutoff, now]. None on transient error.

    GitHub returns releases newest-first and supports per_page=100. We
    page until we see a release older than ``cutoff`` then stop —
    most repos cap out well under a single page anyway.
    """
    count = 0
    page = 1
    while page <= 5:  # cap at 500 releases — overkill for any active repo
        try:
            r = await http.get(
                API.format(owner=owner, repo=repo),
                headers=headers,
                params={"per_page": 100, "page": page},
            )
        except Exception:  # noqa: BLE001
            return None
        if r.status_code == 404:
            # Repo missing or releases tab disabled — treat as zero.
            return 0
        if r.status_code != 200:
            return None
        try:
            items = r.json() or []
        except ValueError:
            return None
        if not isinstance(items, list) or not items:
            break
        crossed_cutoff = False
        for it in items:
            ts = it.get("created_at") or it.get("published_at")
            if not ts:
                continue
            try:
                created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if created < cutoff:
                crossed_cutoff = True
                break
            count += 1
        if crossed_cutoff or len(items) < 100:
            break
        page += 1
    return count
