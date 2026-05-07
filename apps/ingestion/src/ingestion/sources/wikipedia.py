"""wikipedia_views_30d — language-agnostic public-mindshare proxy.

Wikipedia's pageview API publishes daily totals per article going back
to 2015. For the foundation models that have a Wikipedia article (most
top-tier ones do), the 30-day view sum is a clean signal that doesn't
suffer from the same English-language bias as Hacker News mentions.

Match key: ``agent.facts["wikipedia_title"]`` set to the URL-encoded
article title (e.g. ``"GPT-4"``). Population is the discovery
service's job; we no-op for agents lacking that field.

API:
    GET https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article
        /en.wikipedia/all-access/all-agents/{title}/daily/{from}/{to}
    -> items[*].views
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from urllib.parse import quote

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/all-agents/{title}/daily/{since}/{until}"
)


class WikipediaViews30dIngestor(Ingestor):
    name: ClassVar[str] = "wikipedia_views_30d"
    source: ClassVar[SignalSource] = SignalSource.WIKIPEDIA_VIEWS_30D
    tier: ClassVar[str] = "slow"  # daily updates are plenty

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(8)
        now = datetime.now(UTC)
        since = (now - timedelta(days=30)).strftime("%Y%m%d")
        until = now.strftime("%Y%m%d")
        # Wikipedia's REST API expects a descriptive User-Agent (their
        # docs warn that anonymous default UAs may be throttled). The
        # shared httpx client already sends self.settings.user_agent.

        async def one(a: AgentRow) -> SignalReading | None:
            title = (a.facts or {}).get("wikipedia_title") if a.facts else None
            if not title or not isinstance(title, str):
                return None
            async with sem:
                views = await _views(self._http, title, since, until)
            if views is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.WIKIPEDIA_VIEWS_30D,
                value=float(views),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _views(http, title: str, since: str, until: str) -> int | None:
    """Sum of daily pageviews for the article over [since, until]."""
    safe_title = quote(title.replace(" ", "_"), safe="")
    try:
        r = await http.get(API.format(title=safe_title, since=since, until=until))
    except Exception:  # noqa: BLE001
        return None
    if r.status_code == 404:
        # Article doesn't exist — emit 0 so the score reflects "absent
        # from public mindshare" rather than "data missing".
        return 0
    if r.status_code != 200:
        return None
    try:
        data = r.json() or {}
    except ValueError:
        return None
    items = data.get("items") or []
    total = 0
    for it in items:
        v = it.get("views")
        if isinstance(v, (int, float)):
            total += int(v)
    return total
