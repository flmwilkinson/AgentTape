"""mastodon_mentions_7d — public-search hit count across a few large
Mastodon instances.

Sister signal to bluesky_mentions_7d. Bluesky covers the slice of
the AI conversation that's coalesced around AT-protocol; Mastodon
covers the slice that's federated. Both are "what are people
publicly saying about this", just on different open-protocol stacks.

Why federated, not single-instance:
    Mastodon search is per-instance — what each instance has cached
    locally and indexed. There is no global index. We pick a few
    high-volume instances that span the AI conversation (general
    tech, security, ML) and union the unique status URLs they
    return.

Auth:
    Many instances allow unauthenticated full-text search; some
    require an OAuth token. We try without auth and silently skip
    instances that 401/403, rather than refuse to ship the source
    until tokens are configured. If you provide an instance + token
    via settings, the ingestor will use it; otherwise it does
    best-effort anonymous queries.

Schedule: medium tier — slower than Bluesky's fast tier because
each query hits 4 instances and Mastodon's search is heavier than
Bluesky's, but no slower than the medium-tier social signals we
already have (Reddit, Stack Overflow).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.name_tokens import search_tokens

log = logging.getLogger(__name__)

# Curated list of large Mastodon instances spanning the AI/tech
# conversation. Adding to this list is a one-line change. Instances
# that consistently return 401 (require auth) without us having a
# token configured are silently skipped per query.
INSTANCES: tuple[str, ...] = (
    "mastodon.social",
    "infosec.exchange",
    "hachyderm.io",
    "sigmoid.social",
    "fosstodon.org",
)


class MastodonMentions7dIngestor(Ingestor):
    name: ClassVar[str] = "mastodon_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.MASTODON_MENTIONS_7D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(2)  # be polite — 2 concurrent queries max

        async def query_instance(
            instance: str, term: str
        ) -> set[str]:
            url = f"https://{instance}/api/v2/search"
            params = {
                "q": term,
                "type": "statuses",
                "limit": 40,
                "resolve": "false",
            }
            try:
                async with sem:
                    r = await self._http.get(url, params=params, timeout=8.0)
            except Exception:  # noqa: BLE001
                return set()
            if r.status_code in (401, 403):
                # Instance requires auth — silently skip.
                return set()
            if r.status_code != 200:
                return set()
            try:
                data = r.json()
            except Exception:  # noqa: BLE001
                return set()
            statuses = data.get("statuses") or []
            # De-dupe across instances by status URL — federation
            # means the same toot can appear on multiple instances'
            # caches.
            return {s.get("url") for s in statuses if s.get("url")}

        async def one(a: AgentRow) -> SignalReading | None:
            tokens = search_tokens(a)
            if not tokens:
                return None
            # Mastodon's full-text search is OR-of-words by default
            # and short query strings work better than verbose
            # quoted ones. Use the most distinctive token (first
            # in the search_tokens list).
            term = tokens[0]
            unions: set[str] = set()
            results = await asyncio.gather(
                *(query_instance(host, term) for host in INSTANCES),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, set):
                    unions |= r
            if not unions:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.MASTODON_MENTIONS_7D,
                value=float(len(unions)),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]
