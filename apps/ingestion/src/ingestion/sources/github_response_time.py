"""github_first_response_hours_30d — maintainer responsiveness.

A more honest quality signal than close-rate: median hours between
issue creation and the first non-OP comment, across issues opened in
the past 30 days. Catches projects that close stale issues by bot
(high close-rate, low actual responsiveness).

The raw value is hours-to-first-response (lower is better). Scoring
inverts it via a special case in compute.scaled() — anchor 24h ↔ 50,
zero hours ↔ 100, > 7 days ↔ 0.

Cost: per-repo we run one search query (issues opened in 30d, capped
at 30 most recent) plus one comments fetch per issue. With 30 issues
× ~500 repos that's ~15k API calls — slow tier.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

SEARCH = "https://api.github.com/search/issues"
COMMENTS = "https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments"


class GithubFirstResponseHours30dIngestor(Ingestor):
    name: ClassVar[str] = "github_first_response_hours_30d"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_FIRST_RESPONSE_HOURS_30D
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.github_token
        if not token:
            return []
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
            owner, repo = a.github_repo.split("/", 1)
            async with sem:
                hours = await _median_response_hours(
                    self._http, headers, owner, repo, since
                )
            if hours is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.GITHUB_FIRST_RESPONSE_HOURS_30D,
                value=hours,
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _median_response_hours(
    http,
    headers: dict[str, str],
    owner: str,
    repo: str,
    since: str,
) -> float | None:
    """Median hours-to-first-response across issues opened in last 30 days.

    Returns None when there aren't enough issues to compute a stable
    median (< 3) — we'd rather emit nothing than write noise.
    """
    # Get up to 30 most-recent issues opened in the window.
    try:
        r = await http.get(
            SEARCH,
            headers=headers,
            params={
                "q": f"repo:{owner}/{repo} is:issue created:>={since}",
                "sort": "created",
                "order": "desc",
                "per_page": 30,
            },
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        items = (r.json() or {}).get("items") or []
    except ValueError:
        return None
    if not items:
        return None

    # Per-issue: fetch first non-OP comment, compute delta hours. We
    # serialize these inside a per-repo block (the outer semaphore
    # already throttles repos) to stay polite to /search rate limits.
    deltas: list[float] = []
    for it in items:
        number = it.get("number")
        created_at = it.get("created_at")
        author = ((it.get("user") or {}).get("login") or "").lower()
        if not number or not created_at:
            continue
        try:
            opened = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        first = await _first_non_op_comment(
            http, headers, owner, repo, int(number), author
        )
        if first is None:
            continue
        delta_h = max(0.0, (first - opened).total_seconds() / 3600.0)
        deltas.append(delta_h)

    if len(deltas) < 3:
        # Sample too small to be informative — skip rather than emit
        # a wildly variable median.
        return None
    return float(statistics.median(deltas))


async def _first_non_op_comment(
    http,
    headers: dict[str, str],
    owner: str,
    repo: str,
    number: int,
    author: str,
) -> datetime | None:
    """Timestamp of the first comment by anyone other than the OP.

    Bot comments are ignored — many repos have a stale-bot or
    triage-bot that posts within seconds of issue creation, which
    would falsely pin response time near zero.
    """
    try:
        r = await http.get(
            COMMENTS.format(owner=owner, repo=repo, number=number),
            headers=headers,
            params={"per_page": 30},
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        comments = r.json() or []
    except ValueError:
        return None
    if not isinstance(comments, list):
        return None
    for c in comments:
        user = (c.get("user") or {})
        login = (user.get("login") or "").lower()
        if not login or login == author:
            continue
        if user.get("type") == "Bot" or login.endswith("[bot]"):
            continue
        ts = c.get("created_at")
        if not ts:
            continue
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None
