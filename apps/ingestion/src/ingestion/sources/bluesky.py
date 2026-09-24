"""Bluesky mention counts via the authenticated search API.

Bluesky's public search recently went auth-only. We use the standard
account/app-password flow: create a free app password at
https://bsky.app/settings/app-passwords (NOT your main login password)
and set both ``BLUESKY_HANDLE`` and ``BLUESKY_APP_PASSWORD`` in .env.
Without those, the ingestor soft-skips.

The session token issued by Bluesky lasts ~2 hours; we cache it in
process, renew it via refreshSession, and drop it on 401.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.hackernews import fm_hn_phrase

log = logging.getLogger(__name__)

PDS_BASE = "https://bsky.social"
SEARCH_PATH = "/xrpc/app.bsky.feed.searchPosts"
LOGIN_PATH = "/xrpc/com.atproto.server.createSession"
REFRESH_PATH = "/xrpc/com.atproto.server.refreshSession"


class _BskyAuth:
    """Session cache so we don't hit createSession every fetch.

    On a successful login the JWT is cached for ~90 min (Bluesky tokens
    last ~2h; we refresh early to absorb clock skew). On a 429 we
    install a back-off so the next 5-minute fast-tier tick doesn't
    immediately re-login and keep us locked out — Bluesky's rate-limit
    window is short but punishes repeat hits hard, so a single bad
    login can keep the source dark for hours unless we wait it out.
    """

    def __init__(self) -> None:
        self.access_jwt: str | None = None
        # Long-lived (~2 months). Renewing through refreshSession keeps
        # createSession — the tightly rate-limited call (30 / 5 min,
        # 300 / day per account) — to one call per process lifetime.
        self.refresh_jwt: str | None = None
        self.expires_at: float = 0.0
        # Earliest unix-time we're allowed to attempt another login.
        # Bumped on 429 / network failure / non-200.
        self.retry_after: float = 0.0

    async def get(self, http: httpx.AsyncClient, handle: str, password: str) -> str | None:
        now = time.time()
        if self.access_jwt and now < self.expires_at - 60:
            return self.access_jwt
        if now < self.retry_after:
            return None
        if self.refresh_jwt and await self._refresh(http, now):
            return self.access_jwt
        try:
            r = await http.post(
                f"{PDS_BASE}{LOGIN_PATH}",
                json={"identifier": handle, "password": password},
            )
        except Exception:  # noqa: BLE001
            # Network blip — back off briefly, retry next tick.
            self.retry_after = now + 5 * 60
            return None
        if r.status_code == 429:
            # Wait for the window the server names. A flat 1h back-off
            # equalled the fast-tier interval, so every tick re-tried
            # login and the account never left the daily limit.
            self.retry_after = _rate_limit_reset(r, now)
            log.warning(
                "bluesky login rate-limited; backing off for %.0f min. body=%s",
                (self.retry_after - now) / 60,
                r.text[:200],
            )
            return None
        if r.status_code != 200:
            # Auth or transient. Back off 15 min so a misconfigured
            # password doesn't pin the scheduler at full retry rate.
            self.retry_after = now + 15 * 60
            log.warning("bluesky login failed: %d %s", r.status_code, r.text[:200])
            return None
        try:
            data = r.json()
        except ValueError:
            self.retry_after = now + 15 * 60
            return None
        self._store(data, now)
        return self.access_jwt

    async def _refresh(self, http: httpx.AsyncClient, now: float) -> bool:
        try:
            r = await http.post(
                f"{PDS_BASE}{REFRESH_PATH}",
                headers={"Authorization": f"Bearer {self.refresh_jwt}"},
            )
            data = r.json() if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            data = None
        if not data or not data.get("accessJwt"):
            # Expired or revoked — fall through to a full login.
            self.refresh_jwt = None
            return False
        self._store(data, now)
        return True

    def _store(self, data: dict[str, Any], now: float) -> None:
        self.access_jwt = data.get("accessJwt")
        self.refresh_jwt = data.get("refreshJwt") or self.refresh_jwt
        self.expires_at = now + 90 * 60


def _rate_limit_reset(r: Any, now: float) -> float:
    """Unix time the login limit resets, from ``ratelimit-reset``.

    Falls back to 6 h (longer than the hourly tick) when the header is
    missing, and caps at 24 h so a bad header can't disable the source.
    """
    try:
        reset = float(r.headers.get("ratelimit-reset"))
    except (TypeError, ValueError):
        return now + 6 * 60 * 60
    return min(max(reset, now + 5 * 60), now + 24 * 60 * 60)


_AUTH = _BskyAuth()


class BlueskyMentions7dIngestor(Ingestor):
    """Count of Bluesky posts mentioning the agent name in the past 7 days."""

    name: ClassVar[str] = "bluesky_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.BLUESKY_MENTIONS_7D
    tier: ClassVar[str] = "fast"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        handle = self.settings.bluesky_handle
        password = self.settings.bluesky_app_password
        if not (handle and password):
            return []

        token = await _AUTH.get(self._http, handle, password)
        if not token:
            return []

        sem = asyncio.Semaphore(4)
        since = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        headers = {"Authorization": f"Bearer {token}"}

        async def one(a: AgentRow) -> SignalReading | None:
            term = _query_for(a)
            if not term:
                return None
            async with sem:
                count = await _count(self._http, headers, term, since)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.BLUESKY_MENTIONS_7D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


def _query_for(a: AgentRow) -> str | None:
    """Pick the most-distinctive search term for the agent."""
    if a.entity_kind == "foundation_model":
        # Slugs like "openai-gpt-5-2" never appear in posts.
        return fm_hn_phrase(a.name)
    name = a.github_repo or a.slug
    if not name:
        return None
    if "/" in name:
        name = name.split("/", 1)[1]
    name = name.strip()
    return f'"{name}"' if " " in name else name


async def _count(http: httpx.AsyncClient, headers: dict[str, str], query: str, since: str) -> int | None:
    """Return total hits for the query in the past week, or None."""
    params: dict[str, Any] = {"q": query, "limit": 100, "since": since}
    try:
        r = await http.get(f"{PDS_BASE}{SEARCH_PATH}", headers=headers, params=params)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code == 401:
        # Token expired between fetch and now — drop the cached one.
        _AUTH.access_jwt = None
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json() or {}
    except ValueError:
        return None
    posts = data.get("posts") or []
    return len(posts)
