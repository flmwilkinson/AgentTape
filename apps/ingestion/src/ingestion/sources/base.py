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
    """The slice of agents needed by ingestors — anti-corruption layer.

    ``package_names`` carries package-manager identifiers (``npm``,
    ``pypi``, ``cargo``, ``dockerhub``) and ``facts`` holds the
    JSONB-backed enrichment fields (FM modality, ``wikipedia_title``,
    ``discord_invite_code``, …). Both are merge-extensible: adding a
    new ingestor that reads ``package_names["dockerhub"]`` or
    ``facts["wikipedia_title"]`` doesn't require a migration.
    """

    id: UUID
    slug: str
    name: str
    github_repo: str | None
    hf_org: str | None
    hf_model_ids: list[str] | None
    package_names: dict[str, str] | None
    arxiv_ids: list[str] | None
    facts: dict[str, Any] | None
    entity_kind: str


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

        # Slug-by-id lookup so publishers can address `events.agent.<slug>`
        # without an extra DB round-trip per tick.
        slug_by_id = {a.id: a.slug for a in agents}

        written, spiked, changed = 0, 0, 0
        for r in readings:
            slug = slug_by_id.get(r.agent_id)
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
                await _publish_tick(redis_client, r, prior, slug, kind="initial")
                continue

            if prior != r.value:
                changed += 1
                await _publish_tick(redis_client, r, prior, slug, kind="change")

            # Spike: > N× prior and prior > 0 (avoid 0→1 false positives).
            if (
                prior > 0
                and r.value >= prior * self.settings.spike_multiplier
            ):
                spiked += 1
                await _record_spike(session, redis_client, r, prior, slug)

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
    redis_client: Any,
    r: SignalReading,
    prior: float | None,
    slug: str | None,
    kind: str,
) -> None:
    msg = {
        "kind": "signal_changed",
        "tick": kind,
        "agent_id": str(r.agent_id),
        "agent_slug": slug,
        "source": r.source.value,
        "value": r.value,
        "prior": prior,
        "captured_at": r.captured_at.isoformat(),
    }
    body = json.dumps(msg)
    try:
        await redis_client.publish("events.global", body)
        if slug:
            await redis_client.publish(f"events.agent.{slug}", body)
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (tick) failed: %s", e)


async def _record_spike(
    session: AsyncSession,
    redis_client: Any,
    r: SignalReading,
    prior: float,
    slug: str | None,
) -> None:
    payload = {
        "kind": "signal_spike",
        "agent_id": str(r.agent_id),
        "agent_slug": slug,
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
    body = json.dumps(payload)
    try:
        await redis_client.publish("events.global", body)
        if slug:
            await redis_client.publish(f"events.agent.{slug}", body)
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (spike) failed: %s", e)


async def load_admitted_agents(session: AsyncSession) -> list[AgentRow]:
    """Load every admitted agent — the work-list for one ingestion pass.

    Facts are pulled from the most-recent ``discovery_candidates``
    row's ``raw_payload`` rather than a column on agents (the schema
    keeps facts denormalized in raw_payload so we don't have to
    migrate every time a new fact-key shows up — Wikipedia title,
    Discord invite code, OpenRouter id, etc. all read from there).
    """
    rows = await session.execute(
        text(
            """
            SELECT a.id, a.slug, a.name, a.github_repo, a.hf_org,
                   a.hf_model_ids, a.package_names, a.arxiv_ids,
                   a.entity_kind,
                   dc.raw_payload AS facts
            FROM agents a
            LEFT JOIN LATERAL (
                SELECT raw_payload FROM discovery_candidates
                WHERE promoted_to_agent_id = a.id
                ORDER BY found_at DESC LIMIT 1
            ) dc ON true
            WHERE a.eligibility_status = 'admitted'
            """
        )
    )
    out: list[AgentRow] = []
    for r in rows:
        out.append(
            AgentRow(
                id=r[0],
                slug=r[1],
                name=r[2],
                github_repo=r[3],
                hf_org=r[4],
                hf_model_ids=r[5],
                package_names=r[6],
                arxiv_ids=r[7],
                entity_kind=r[8],
                facts=r[9],
            )
        )
    return out


async def open_redis(settings: Settings) -> Any:
    return redis_async.from_url(settings.redis_url, decode_responses=True)
