"""Product Hunt upvote count.

For agents that we suspect launched on Product Hunt (most SaaS-shaped
AI agents do), look up the post and record its upvote total. Free
GraphQL API, requires an OAuth token via
https://api.producthunt.com/v2/oauth/applications. Soft-skips when
``PRODUCT_HUNT_TOKEN`` is unset.

This is the earliest adoption signal for SaaS agents that don't yet
have GitHub repos or HF mirrors — it sees them on launch day.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

# We pick the agent's most-distinctive name and try to match it to a
# Product Hunt slug. Misses are silently dropped — there's no point
# emitting zero readings for agents that aren't on the platform.
LOOKUP_QUERY = """
query LookupPost($slug: String!) {
  post(slug: $slug) {
    id
    name
    votesCount
  }
}
"""


class ProductHuntUpvotesIngestor(Ingestor):
    """Cumulative upvote count for the agent's Product Hunt listing."""

    name: ClassVar[str] = "producthunt_upvotes"
    source: ClassVar[SignalSource] = SignalSource.PRODUCTHUNT_UPVOTES
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.product_hunt_token
        if not token:
            return []

        sem = asyncio.Semaphore(2)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": self.settings.user_agent,
        }

        async def one(a: AgentRow) -> SignalReading | None:
            slug = _slug_for(a)
            if not slug:
                return None
            async with sem:
                votes = await _votes(self._http, headers, slug)
            if votes is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.PRODUCTHUNT_UPVOTES,
                value=float(votes),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


def _slug_for(a: AgentRow) -> str | None:
    """Best guess at the Product Hunt slug for this agent.

    PH slugs are kebab-case lowercased. Our internal slug is already
    in that shape (for application agents) so we use it directly. For
    foundation models the slug carries a provider prefix that PH
    wouldn't use, so we trim it. Lookups that don't match return null
    cleanly — we just drop the reading.
    """
    if not a.slug:
        return None
    slug = a.slug.lower()
    # Strip a trailing "-1", "-2" we may have added at admit time.
    while slug and slug[-1].isdigit() and len(slug) > 4 and slug[-2] == "-":
        slug = slug[:-2]
    return slug


async def _votes(http, headers: dict[str, str], slug: str) -> int | None:
    try:
        r = await http.post(
            GRAPHQL_URL,
            headers=headers,
            json={"query": LOOKUP_QUERY, "variables": {"slug": slug}},
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        data: dict[str, Any] = r.json() or {}
    except ValueError:
        return None
    post = (data.get("data") or {}).get("post")
    if not post:
        return None
    return int(post.get("votesCount") or 0)
