"""discord_members — community-size signal for OSS agents.

The cheapest fix for "1k stars but ghost town" agents. Discord publicly
exposes ``approximate_member_count`` and ``approximate_presence_count``
on any invite link (no auth, no scopes), so we just hit the invite
endpoint with ``with_counts=true``.

Match key: ``agent.facts["discord_invite_code"]`` set to the bare invite
code (e.g. ``"abc123"`` from ``discord.gg/abc123``). The discovery
service is responsible for harvesting this from project README links
when present.

API:
    GET https://discord.com/api/v10/invites/{code}?with_counts=true
    -> approximate_member_count, approximate_presence_count
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = "https://discord.com/api/v10/invites/{code}"


class DiscordMembersIngestor(Ingestor):
    name: ClassVar[str] = "discord_members"
    source: ClassVar[SignalSource] = SignalSource.DISCORD_MEMBERS
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(8)

        async def one(a: AgentRow) -> SignalReading | None:
            code = (a.facts or {}).get("discord_invite_code") if a.facts else None
            if not code or not isinstance(code, str):
                return None
            async with sem:
                count = await _members(self._http, code)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.DISCORD_MEMBERS,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _members(http, code: str) -> int | None:
    """Approximate member count for the invite, or None on error.

    A stale or revoked invite returns 404 — we treat that as "data
    missing" rather than 0 so a temporarily-broken invite doesn't
    overwrite the real community size.
    """
    try:
        r = await http.get(API.format(code=code), params={"with_counts": "true"})
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json() or {}
    except ValueError:
        return None
    val = data.get("approximate_member_count")
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
