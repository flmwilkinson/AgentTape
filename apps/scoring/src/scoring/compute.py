"""Score computation.

The scoring algorithm is split into three phases:

1. **Population stats** — for every signal source, compute the population
   mean and stddev across the latest reading per agent. We z-score within
   the admitted population, NOT against an absolute baseline. This is
   recomputed once per recompute batch, not per-agent.

2. **Per-agent pillars** — Adoption, Quality, Momentum, Community. Each
   pillar takes its source's latest reading, z-scores it, clamps to
   [-3, +3] and min-max scales to [0, 100]. Quality is special: if the
   agent has no benchmark_results we return ``None`` ("Unrated") rather
   than 0.

3. **Headline AgentScore** — weighted blend of the four. If quality is
   unrated, its 30% weight is redistributed pro rata across the other
   three so unrated agents aren't penalized.

Manipulation resistance: any signal flagged on ``agents.manipulation_flags``
is excluded from that day's score for that agent. ``manipulation_resistance``
is a confidence in [0, 1]: 1.0 with no flags, decreasing as flags accumulate.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scoring.config import Settings, get_settings
from scoring.enums import (
    ADOPTION_SOURCES,
    COMMUNITY_SOURCES,
    MOMENTUM_SOURCES,
    SignalSource,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- types


@dataclass
class PillarScores:
    adoption: float
    quality: float | None
    momentum: float
    community: float
    manipulation_resistance: float
    agent_score: float
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class PopulationStats:
    """Mean and stddev per signal source across all admitted agents."""

    means: dict[SignalSource, float]
    stds: dict[SignalSource, float]
    benchmark_mean: float | None
    benchmark_std: float | None


# ---------------------------------------------------------------- queries


async def _latest_value(
    session: AsyncSession, agent_id: UUID, source: SignalSource
) -> float | None:
    r = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid AND source = CAST(:src AS signal_source)
            ORDER BY captured_at DESC LIMIT 1
            """
        ),
        {"aid": agent_id, "src": source.value},
    )
    row = r.first()
    return float(row[0]) if row else None


async def _value_at(
    session: AsyncSession,
    agent_id: UUID,
    source: SignalSource,
    *,
    days_ago: int,
) -> float | None:
    cutoff = datetime.now(UTC) - timedelta(days=days_ago)
    r = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid
              AND source = CAST(:src AS signal_source)
              AND captured_at <= :cutoff
            ORDER BY captured_at DESC LIMIT 1
            """
        ),
        {"aid": agent_id, "src": source.value, "cutoff": cutoff},
    )
    row = r.first()
    return float(row[0]) if row else None


async def _agent_benchmark_score(
    session: AsyncSession, agent_id: UUID
) -> float | None:
    """Latest benchmark_results value averaged across all benchmarks the agent appears on."""
    r = await session.execute(
        text(
            """
            WITH latest AS (
                SELECT benchmark_id, score,
                       ROW_NUMBER() OVER (
                           PARTITION BY benchmark_id
                           ORDER BY captured_at DESC
                       ) AS rn
                FROM benchmark_results
                WHERE agent_id = :aid
            )
            SELECT avg(score) FROM latest WHERE rn = 1
            """
        ),
        {"aid": agent_id},
    )
    row = r.first()
    return float(row[0]) if row and row[0] is not None else None


async def _population_for_source(
    session: AsyncSession, source: SignalSource
) -> tuple[float, float]:
    """Mean + stddev across the latest reading per admitted agent."""
    r = await session.execute(
        text(
            """
            WITH latest AS (
                SELECT agent_id, value,
                       ROW_NUMBER() OVER (
                           PARTITION BY agent_id ORDER BY captured_at DESC
                       ) AS rn
                FROM signals
                WHERE source = CAST(:src AS signal_source)
            )
            SELECT avg(value)::float, stddev_pop(value)::float
            FROM latest
            JOIN agents a ON a.id = latest.agent_id
            WHERE rn = 1 AND a.eligibility_status = 'admitted'
            """
        ),
        {"src": source.value},
    )
    mean, std = r.first() or (0.0, 0.0)
    return float(mean or 0.0), float(std or 0.0)


async def _benchmark_population(
    session: AsyncSession,
) -> tuple[float | None, float | None]:
    r = await session.execute(
        text(
            """
            WITH latest AS (
                SELECT agent_id, benchmark_id, score,
                       ROW_NUMBER() OVER (
                           PARTITION BY agent_id, benchmark_id
                           ORDER BY captured_at DESC
                       ) AS rn
                FROM benchmark_results
            ),
            per_agent AS (
                SELECT agent_id, avg(score) AS s FROM latest WHERE rn = 1 GROUP BY agent_id
            )
            SELECT avg(s)::float, stddev_pop(s)::float FROM per_agent
            """
        )
    )
    row = r.first() or (None, None)
    return (
        float(row[0]) if row[0] is not None else None,
        float(row[1]) if row[1] is not None else None,
    )


async def population_stats(session: AsyncSession) -> PopulationStats:
    sources = {*ADOPTION_SOURCES, *COMMUNITY_SOURCES, *MOMENTUM_SOURCES}
    means: dict[SignalSource, float] = {}
    stds: dict[SignalSource, float] = {}
    for src in sources:
        m, s = await _population_for_source(session, src)
        means[src] = m
        stds[src] = s
    bm, bs = await _benchmark_population(session)
    return PopulationStats(means=means, stds=stds, benchmark_mean=bm, benchmark_std=bs)


# ---------------------------------------------------------------- math


def _z(value: float, mean: float, std: float) -> float:
    if std <= 0:
        return 0.0
    return (value - mean) / std


def _scaled(z: float) -> float:
    """Clamp z to [-3, +3] then map to [0, 100]."""
    z = max(-3.0, min(3.0, z))
    return (z + 3.0) / 6.0 * 100.0


def _blend(values: list[float], weights: list[float] | None = None) -> float:
    if not values:
        return 0.0
    if weights is None:
        weights = [1.0] * len(values)
    total_w = sum(weights)
    if total_w == 0:
        return 0.0
    return sum(v * w for v, w in zip(values, weights, strict=True)) / total_w


# --------------------------------------------------- per-pillar helpers


def _excluded_sources(manipulation_flags: dict | None) -> set[SignalSource]:
    """Translate manipulation_flags into the set of signal sources to skip.

    ``ingestion/integrity.py`` writes flag rules keyed by name. We map
    each rule to the upstream signals it implicates so the recompute
    excludes exactly those readings for this agent today.
    """
    if not manipulation_flags:
        return set()
    out: set[SignalSource] = set()
    rule_to_sources: dict[str, list[SignalSource]] = {
        "star_spike_no_contrib_diversity": [SignalSource.GITHUB_STARS],
        "hf_surge_no_github": [SignalSource.HF_DOWNLOADS_30D],
        "coordinated_hn_posting": [
            SignalSource.HN_MENTIONS_7D,
            SignalSource.HN_POINTS_7D,
        ],
    }
    for rule in manipulation_flags:
        out.update(rule_to_sources.get(rule, []))
    return out


def _manipulation_resistance(manipulation_flags: dict | None) -> float:
    if not manipulation_flags:
        return 1.0
    n = len(manipulation_flags)
    # Each active flag knocks ~25% off confidence, never below 0.1.
    return max(0.1, 1.0 - 0.25 * n)


# ---------------------------------------------------------------- pillars


async def _adoption(
    session: AsyncSession,
    agent_id: UUID,
    pop: PopulationStats,
    excluded: set[SignalSource],
) -> tuple[float, dict[str, Any]]:
    inputs: dict[str, Any] = {}
    contribs: list[float] = []
    for src in ADOPTION_SOURCES:
        if src in excluded:
            inputs[src.value] = "excluded"
            continue
        v = await _latest_value(session, agent_id, src)
        if v is None:
            inputs[src.value] = None
            continue
        z = _z(v, pop.means[src], pop.stds[src])
        scaled = _scaled(z)
        inputs[src.value] = {"value": v, "z": z, "scaled": scaled}
        contribs.append(scaled)
    return _blend(contribs), inputs


async def _quality(
    session: AsyncSession,
    agent_id: UUID,
    pop: PopulationStats,
) -> tuple[float | None, dict[str, Any]]:
    """Mean z-score across all benchmarks the agent appears on."""
    score = await _agent_benchmark_score(session, agent_id)
    if score is None or pop.benchmark_mean is None or pop.benchmark_std is None:
        return None, {"raw": score, "rated": False}
    z = _z(score, pop.benchmark_mean, pop.benchmark_std)
    return _scaled(z), {"raw": score, "z": z, "rated": True}


async def _momentum(
    session: AsyncSession,
    agent_id: UUID,
    excluded: set[SignalSource],
) -> tuple[float, dict[str, Any]]:
    """7d + 30d rate-of-change blend over adoption signals."""
    inputs: dict[str, Any] = {}
    contribs: list[float] = []
    weights: list[float] = []
    for src in MOMENTUM_SOURCES:
        if src in excluded:
            inputs[src.value] = "excluded"
            continue
        now_v = await _latest_value(session, agent_id, src)
        v_7d = await _value_at(session, agent_id, src, days_ago=7)
        v_30d = await _value_at(session, agent_id, src, days_ago=30)
        if now_v is None:
            inputs[src.value] = None
            continue
        roc_7 = _rate_of_change(now_v, v_7d)
        roc_30 = _rate_of_change(now_v, v_30d)
        # Map a ROC to [0, 100]: 0% growth -> 50; +100% -> 100; -50% -> 0.
        contrib_7 = _roc_scaled(roc_7) if roc_7 is not None else None
        contrib_30 = _roc_scaled(roc_30) if roc_30 is not None else None
        # 60/40 blend of 7d:30d when both are present, else the available one.
        if contrib_7 is None and contrib_30 is None:
            inputs[src.value] = {"roc_7d": None, "roc_30d": None}
            continue
        if contrib_7 is not None and contrib_30 is not None:
            value = 0.6 * contrib_7 + 0.4 * contrib_30
        else:
            value = contrib_7 if contrib_7 is not None else contrib_30
        inputs[src.value] = {
            "now": now_v,
            "v_7d": v_7d,
            "v_30d": v_30d,
            "roc_7d": roc_7,
            "roc_30d": roc_30,
            "scaled": value,
        }
        contribs.append(value)  # type: ignore[arg-type]
        weights.append(1.0)
    if not contribs:
        # Neutral 50 when we have no momentum data (don't punish brand-new agents).
        return 50.0, {"reason": "no_momentum_data"}
    return _blend(contribs, weights), inputs


async def _community(
    session: AsyncSession,
    agent_id: UUID,
    pop: PopulationStats,
    excluded: set[SignalSource],
) -> tuple[float, dict[str, Any]]:
    inputs: dict[str, Any] = {}
    contribs: list[float] = []
    for src in COMMUNITY_SOURCES:
        if src in excluded:
            inputs[src.value] = "excluded"
            continue
        v = await _latest_value(session, agent_id, src)
        if v is None:
            inputs[src.value] = None
            continue
        z = _z(v, pop.means[src], pop.stds[src])
        scaled = _scaled(z)
        inputs[src.value] = {"value": v, "z": z, "scaled": scaled}
        contribs.append(scaled)
    return _blend(contribs) if contribs else 50.0, inputs


def _rate_of_change(now: float | None, then: float | None) -> float | None:
    if now is None or then is None or then <= 0:
        return None
    return (now - then) / then


def _roc_scaled(roc: float) -> float:
    """Map ROC to [0, 100] with 0% -> 50."""
    # +/- 100% caps the scale. 0 -> 50, +1.0 -> 100, -1.0 -> 0, beyond clamps.
    return max(0.0, min(100.0, 50.0 + roc * 50.0))


# ---------------------------------------------------------------- headline


def _headline(
    pillars: PillarScores, settings: Settings
) -> float:
    """Weighted blend; redistribute quality's weight if unrated."""
    weights = {
        "adoption": settings.weight_adoption,
        "quality": settings.weight_quality,
        "momentum": settings.weight_momentum,
        "community": settings.weight_community,
    }
    if pillars.quality is None:
        # Spread quality's weight pro-rata across the other three.
        spare = weights["quality"]
        weights["quality"] = 0.0
        non_zero = [k for k in ("adoption", "momentum", "community")]
        scaler = sum(weights[k] for k in non_zero)
        if scaler > 0:
            for k in non_zero:
                weights[k] += spare * (weights[k] / scaler)

    parts = [
        weights["adoption"] * pillars.adoption,
        weights["quality"] * (pillars.quality or 0.0),
        weights["momentum"] * pillars.momentum,
        weights["community"] * pillars.community,
    ]
    return float(sum(parts))


# ---------------------------------------------------------------- public


async def compute_for_agent(
    session: AsyncSession,
    agent_id: UUID,
    pop: PopulationStats,
    settings: Settings | None = None,
) -> PillarScores:
    settings = settings or get_settings()
    flags = await _agent_flags(session, agent_id)
    excluded = _excluded_sources(flags)
    resistance = _manipulation_resistance(flags)

    adoption, adoption_in = await _adoption(session, agent_id, pop, excluded)
    quality, quality_in = await _quality(session, agent_id, pop)
    momentum, momentum_in = await _momentum(session, agent_id, excluded)
    community, community_in = await _community(session, agent_id, pop, excluded)

    pillars = PillarScores(
        adoption=adoption,
        quality=quality,
        momentum=momentum,
        community=community,
        manipulation_resistance=resistance,
        agent_score=0.0,
        inputs={
            "adoption": adoption_in,
            "quality": quality_in,
            "momentum": momentum_in,
            "community": community_in,
            "excluded": [s.value for s in excluded],
            "manipulation_flags": list(flags or {}),
        },
    )
    pillars.agent_score = _headline(pillars, settings)
    return pillars


async def _agent_flags(session: AsyncSession, agent_id: UUID) -> dict | None:
    r = await session.execute(
        text("SELECT manipulation_flags FROM agents WHERE id = :id"),
        {"id": agent_id},
    )
    row = r.first()
    return row[0] if row and row[0] else None


# --------------------------------------------------------- persist + batch


async def persist_score(
    session: AsyncSession, agent_id: UUID, pillars: PillarScores
) -> UUID:
    r = await session.execute(
        text(
            """
            INSERT INTO scores (
                id, agent_id, computed_at,
                agent_score, adoption, quality, momentum, community,
                manipulation_resistance
            ) VALUES (
                gen_random_uuid(), :aid, now(),
                :a, :ad, :q, :m, :c, :mr
            ) RETURNING id
            """
        ),
        {
            "aid": agent_id,
            "a": pillars.agent_score,
            "ad": pillars.adoption,
            "q": pillars.quality,
            "m": pillars.momentum,
            "c": pillars.community,
            "mr": pillars.manipulation_resistance,
        },
    )
    return r.scalar_one()


async def recompute_agents(
    session: AsyncSession,
    agent_ids: Iterable[UUID],
    redis_client: Any,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Recompute one batch of agents using shared population stats."""
    settings = settings or get_settings()
    pop = await population_stats(session)

    written = 0
    rank_changes = 0
    for aid in agent_ids:
        # Snapshot the prior headline for change detection.
        prior = await _prior_headline(session, aid)
        pillars = await compute_for_agent(session, aid, pop, settings)
        await persist_score(session, aid, pillars)
        written += 1

        if prior is None or _significant_change(prior, pillars.agent_score):
            rank_changes += 1
            await _emit_score_changed(session, redis_client, aid, prior, pillars)

    await session.commit()
    log.info("scoring: recomputed %d agents (%d notable changes)", written, rank_changes)
    return {"recomputed": written, "notable_changes": rank_changes}


async def _prior_headline(session: AsyncSession, agent_id: UUID) -> float | None:
    r = await session.execute(
        text(
            """
            SELECT agent_score FROM scores
            WHERE agent_id = :aid
            ORDER BY computed_at DESC LIMIT 1 OFFSET 1
            """
        ),
        {"aid": agent_id},
    )
    row = r.first()
    return float(row[0]) if row else None


def _significant_change(prior: float, now: float) -> bool:
    return abs(now - prior) >= 1.0  # >=1 point on the 0-100 scale


async def _emit_score_changed(
    session: AsyncSession,
    redis_client: Any,
    agent_id: UUID,
    prior: float | None,
    pillars: PillarScores,
) -> None:
    payload = {
        "agent_id": str(agent_id),
        "agent_score": pillars.agent_score,
        "prior": prior,
        "adoption": pillars.adoption,
        "quality": pillars.quality,
        "momentum": pillars.momentum,
        "community": pillars.community,
        "manipulation_resistance": pillars.manipulation_resistance,
    }
    await session.execute(
        text(
            """
            INSERT INTO events (id, kind, agent_id, payload)
            VALUES (gen_random_uuid(), CAST('score_changed' AS event_kind),
                    :aid, CAST(:p AS jsonb))
            """
        ),
        {"aid": agent_id, "p": json.dumps(payload)},
    )
    try:
        await redis_client.publish("tape:scores", json.dumps(payload))
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (score_changed) failed: %s", e)


async def all_admitted_agent_ids(session: AsyncSession) -> list[UUID]:
    r = await session.execute(
        text("SELECT id FROM agents WHERE eligibility_status = 'admitted'")
    )
    return [row[0] for row in r]
