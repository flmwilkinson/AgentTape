"""Reddit ingestors — OAuth required.

Reddit's anonymous endpoints are heavily rate-limited and routinely 403
the User-Agent strings used by HTTP libraries. We use the standard
client_credentials OAuth flow with a small token cache; if the env vars
aren't set we soft-skip the whole source so the medium tier doesn't
fail.
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


class _RedditAuth:
    """Tiny token cache so we don't hit /access_token on every fetch."""

    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: float = 0.0

    async def get(
        self, http, client_id: str, client_secret: str, user_agent: str
    ) -> str | None:
        if self.token and time.time() < self.expires_at - 60:
            return self.token
        try:
            r = await http.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"User-Agent": user_agent},
            )
        except Exception:  # noqa: BLE001
            return None
        if r.status_code != 200:
            return None
        data = r.json()
        self.token = data.get("access_token")
        self.expires_at = time.time() + (data.get("expires_in") or 3600)
        return self.token


_AUTH = _RedditAuth()


async def _search(
    http, ua: str, token: str, query: str, since_ts: int
) -> dict | None:
    try:
        r = await http.get(
            "https://oauth.reddit.com/search.json",
            params={
                "q": query,
                "sort": "new",
                "limit": 100,
                "t": "week",
                "restrict_sr": "false",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": ua,
            },
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    return r.json()


class _RedditIngestor(Ingestor):
    """Shared base — concrete subclasses set the aggregate field."""

    @property
    def _aggregate(self) -> str:
        raise NotImplementedError

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        cid = self.settings.reddit_client_id
        csec = self.settings.reddit_client_secret
        if not (cid and csec):
            return []
        token = await _AUTH.get(self._http, cid, csec, self.settings.user_agent)
        if not token:
            return []
        since = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
        sem = asyncio.Semaphore(3)

        async def one(a: AgentRow) -> SignalReading | None:
            term = a.github_repo or a.slug
            if not term:
                return None
            async with sem:
                data = await _search(
                    self._http, self.settings.user_agent, token, term, since
                )
            if not data:
                return None
            posts = (data.get("data") or {}).get("children") or []
            posts = [p["data"] for p in posts if isinstance(p, dict)]
            posts = [p for p in posts if (p.get("created_utc") or 0) >= since]

            if self._aggregate == "mentions":
                value = float(len(posts))
            elif self._aggregate == "points":
                value = float(sum((p.get("score") or 0) for p in posts))
            else:
                return None
            return SignalReading(
                agent_id=a.id,
                source=self.source,
                value=value,
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


class RedditMentions7dIngestor(_RedditIngestor):
    name: ClassVar[str] = "reddit_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.REDDIT_MENTIONS_7D
    tier: ClassVar[str] = "medium"
    _aggregate = "mentions"


class RedditPoints7dIngestor(_RedditIngestor):
    name: ClassVar[str] = "reddit_points_7d"
    source: ClassVar[SignalSource] = SignalSource.REDDIT_POINTS_7D
    tier: ClassVar[str] = "medium"
    _aggregate = "points"
