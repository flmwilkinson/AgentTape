"""Ingestor base class.

Each ingestor implements ``fetch`` (one batch of readings for a list of
admitted agents) and ``normalize`` (turn the upstream payload into a
list of :class:`SignalReading`). The base class handles ``persist``:
the append-only INSERT into ``signals``, the spike check against the
prior reading, and the Redis pub/sub fan-out — so individual sources
never have to think about that plumbing.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

import httpx
import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import Settings
from ingestion.enums import SignalSource

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentRow:
    """The slice of agents needed by ingestors — anti-corruption layer."""

    id: UUID
    slug: str
    github_repo: str | None
    hf_org: str | None
    hf_model_ids: list[str] | None
    package_names: dict[str, str] | None  # {"npm": "...", "pypi": "..."}
    arxiv_ids: list[str] | None


@dataclass
class SignalReading:
    agent_id: UUID
    source: SignalSource
    value: float
    captured_at: datetime


class Ingestor(ABC):
    """Base class — subclass per signal kind, not per upstream API."""

    name: ClassVar[str]
    source: ClassVar[SignalSource]
    tier: ClassVar[str]  # "fast" | "medium" | "slow"

    def __init__(
        self, settings: Settings, http: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings
        self._http_owned = http is None
        self._http = http or httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        if self._http_owned:
            await self._http.aclose()

    @abstractmethod
    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        """Return readings for the agents this ingestor can speak to.

        Implementations should silently drop agents lacking the relevant
        fields (e.g. github ingestors skip agents with no github_repo).
        """

    async def run(
        self, session: AsyncSession, agents: list[AgentRow], redis_client: Any
    ) -> dict[str, int]:
        """One pass: fetch, persist (with spike detection), publish events."""
        try:
            readings = await self.fetch(agents)
        except Exception:  # noqa: BLE001 — one bad source can't kill the tier
            log.exception("ingestor %s fetch failed", self.name)
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}

        written, spiked, changed = 0, 0, 0
        for r in readings:
            prior = await _last_value(session, r.agent_id, r.source)
            await session.execute(
                text(
                    """
                    INSERT INTO signals (id, captured_at, agent_id, source, value)
                    VALUES (gen_random_uuid(), :ts, :aid, CAST(:src AS signal_source), :val)
                    """
                ),
                {
                    "ts": r.captured_at,
                    "aid": r.agent_id,
                    "src": r.source.value,
                    "val": r.value,
                },
            )
            written += 1

            if prior is None:
                # First reading: tick the dashboard but don't claim it's a spike.
                await _publish_tick(redis_client, r, prior, kind="initial")
                continue

            if prior != r.value:
                changed += 1
                await _publish_tick(redis_client, r, prior, kind="change")

            # Spike: > N× prior and prior > 0 (avoid 0→1 false positives).
            if (
                prior > 0
                and r.value >= prior * self.settings.spike_multiplier
            ):
                spiked += 1
                await _record_spike(session, redis_client, r, prior)

        await session.commit()
        log.info(
            "ingestor %s: %d readings, %d written, %d changed, %d spiked",
            self.name,
            len(readings),
            written,
            changed,
            spiked,
        )
        return {
            "fetched": len(readings),
            "written": written,
            "spiked": spiked,
            "changed": changed,
        }


# ---------------------------------------------------------------- helpers


async def _last_value(
    session: AsyncSession, agent_id: UUID, source: SignalSource
) -> float | None:
    """The most recent prior value for (agent, source), or None."""
    result = await session.execute(
        text(
            """
            SELECT value
            FROM signals
            WHERE agent_id = :aid AND source = CAST(:src AS signal_source)
            ORDER BY captured_at DESC
            LIMIT 1
            """
        ),
        {"aid": agent_id, "src": source.value},
    )
    row = result.first()
    return float(row[0]) if row else None


async def _publish_tick(
    redis_client: Any, r: SignalReading, prior: float | None, kind: str
) -> None:
    msg = {
        "type": "tick",
        "kind": kind,
        "agent_id": str(r.agent_id),
        "source": r.source.value,
        "value": r.value,
        "prior": prior,
        "captured_at": r.captured_at.isoformat(),
    }
    try:
        await redis_client.publish("tape:ticks", json.dumps(msg))
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (tick) failed: %s", e)


async def _record_spike(
    session: AsyncSession,
    redis_client: Any,
    r: SignalReading,
    prior: float,
) -> None:
    payload = {
        "agent_id": str(r.agent_id),
        "source": r.source.value,
        "prior": prior,
        "value": r.value,
        "multiplier": (r.value / prior) if prior else None,
        "captured_at": r.captured_at.isoformat(),
    }
    await session.execute(
        text(
            """
            INSERT INTO events (id, kind, agent_id, payload)
            VALUES (gen_random_uuid(), CAST('signal_spike' AS event_kind), :aid, CAST(:p AS jsonb))
            """
        ),
        {"aid": r.agent_id, "p": json.dumps(payload)},
    )
    try:
        await redis_client.publish(
            "tape:ticks",
            json.dumps({"type": "spike", **payload}),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (spike) failed: %s", e)


async def load_admitted_agents(session: AsyncSession) -> list[AgentRow]:
    """Load every admitted agent — the work-list for one ingestion pass."""
    rows = await session.execute(
        text(
            """
            SELECT id, slug, github_repo, hf_org, hf_model_ids,
                   package_names, arxiv_ids
            FROM agents
            WHERE eligibility_status = 'admitted'
            """
        )
    )
    out: list[AgentRow] = []
    for r in rows:
        out.append(
            AgentRow(
                id=r[0],
                slug=r[1],
                github_repo=r[2],
                hf_org=r[3],
                hf_model_ids=r[4],
                package_names=r[5],
                arxiv_ids=r[6],
            )
        )
    return out


async def open_redis(settings: Settings) -> Any:
    return redis_async.from_url(settings.redis_url, decode_responses=True)
