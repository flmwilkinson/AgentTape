"""Unified score computation.

One formula for both application agents and foundation models. No
metadata-derived inflation. Every point of every pillar maps to a
specific signal reading the agent has on file.

The maths
---------

For any count-shaped signal S with raw value v and an absolute
"value-where-it-scores-50" anchor:

    scaled(v, anchor) = min(100, 50 * log10(v + 1) / log10(anchor + 1))

That gives a stable 0–100 score per signal that doesn't depend on
the population of other agents. A model with 100k HF downloads
scores 50 forever, regardless of who else is in the dataset.

Pillar score = arithmetic mean of available scaled signals bound to
that pillar. If no signals are present for a pillar, the pillar is
**null** (Unrated). The headline AgentScore is the weight-blended
mean of the non-null pillars; if all four are null, the agent is
Unrated as a whole.

Pillar source list differs by entity_kind (see PILLAR_SOURCES) but
the arithmetic is identical, so two scores are directly comparable
across kinds.
"""
from __future__ import annotations

import json
import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scoring.config import Settings, get_settings
from scoring.enums import SignalSource

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- types


@dataclass
class PillarScores:
    adoption: float | None
    quality: float | None
    momentum: float | None
    community: float | None
    manipulation_resistance: float
    agent_score: float | None
    inputs: dict[str, Any] = field(default_factory=dict)


# Kept for backwards-compat with the recompute call signature; the
# new formula doesn't actually need population stats but the
# subscriber/scheduler call passes it.
@dataclass
class PopulationStats:
    placeholder: bool = True


# ----------------------------------------------------------- anchor table

# Each anchor is the raw value at which the signal scores exactly 50.
# Lower values curve toward 0; higher values flatten toward 100. These
# numbers are documented on the public methodology page so readers can
# argue with them.
ANCHORS: dict[SignalSource, float] = {
    SignalSource.GITHUB_STARS: 1_000,
    SignalSource.GITHUB_FORKS: 200,
    SignalSource.GITHUB_CONTRIBUTORS: 30,
    SignalSource.GITHUB_COMMITS_7D: 50,
    SignalSource.GITHUB_MENTIONS_7D: 20,
    SignalSource.HF_DOWNLOADS_30D: 100_000,
    SignalSource.HF_LIKES: 200,
    SignalSource.NPM_WEEKLY: 1_000,
    SignalSource.PYPI_MONTHLY: 10_000,
    SignalSource.HN_MENTIONS_7D: 10,
    SignalSource.HN_POINTS_7D: 100,
    SignalSource.REDDIT_MENTIONS_7D: 10,
    SignalSource.REDDIT_POINTS_7D: 100,
    SignalSource.BLUESKY_MENTIONS_7D: 10,
    SignalSource.STACKOVERFLOW_QUESTIONS_7D: 5,
    SignalSource.PRODUCTHUNT_UPVOTES: 100,
    SignalSource.ARXIV_CITATIONS: 100,
    # Migration 0007 — Priority A/B/C signals.
    # Docker pull_count is lifetime cumulative; 100k is the inflection
    # point for "self-hosted agents people are actually deploying".
    SignalSource.DOCKER_PULLS_30D: 100_000,
    SignalSource.CRATES_DOWNLOADS_90D: 10_000,
    # GitHub releases per 90 days. 6 = "one every two weeks" = 50.
    SignalSource.GITHUB_RELEASES_90D: 6,
    # Issue close-rate signal is already pre-multiplied by 100, so
    # 100 == 1:1 close-to-open which deserves the median 50 anchor.
    SignalSource.GITHUB_ISSUE_CLOSE_RATE_30D: 100,
    # Wikipedia 30d sum. 100k = a real public footprint (top FMs).
    SignalSource.WIKIPEDIA_VIEWS_30D: 100_000,
    SignalSource.DISCORD_MEMBERS: 5_000,
    # Google Trends is 0–100 already; treat as already-scaled, anchor
    # at 30 so a sustained mid-interest term (~30) reads as 50.
    SignalSource.GOOGLE_TRENDS_SCORE: 30,
    # Migration 0008.
    # OpenRouter monthly token volume. The traffic distribution is
    # extremely fat-tailed — top models clear hundreds of billions.
    # 1B tokens is "real production usage but not a flagship" = 50.
    SignalSource.OPENROUTER_TOKEN_VOLUME_30D: 1_000_000_000,
    # github_first_response_hours_30d uses an INVERSE special case in
    # scaled() — anchor here is the value-where-the-score-is-50.
    # 24h ↔ 50 means "a one-day median response is the par baseline".
    SignalSource.GITHUB_FIRST_RESPONSE_HOURS_30D: 24,
}


def scaled(value: float, source: SignalSource) -> float:
    """Map a raw signal value to a 0–100 score via log-anchor curve."""
    if source == SignalSource.BENCHMARK_SCORE:
        # Benchmarks already publish on a 0–100 scale.
        return max(0.0, min(100.0, value))
    if source == SignalSource.MCP_REGISTRY_LISTED:
        # Binary signal: listed (1) → 75, not listed (0) → 0.
        return 75.0 if value > 0 else 0.0
    if source == SignalSource.HF_TRENDING_RANK:
        # Inverted: rank 1 = best, anchor at rank 10 = 50. Use the
        # same log curve but on the inverse scale.
        if value <= 0:
            return 50.0
        # rank 1 → ~85, rank 10 → 50, rank 100 → ~0
        return max(0.0, min(100.0, 100.0 - 50.0 * math.log10(value) / math.log10(10)))
    if source == SignalSource.GITHUB_FIRST_RESPONSE_HOURS_30D:
        # Inverted: 0h ≈ 100 (instant), anchor 24h = 50, > 7d ≈ 0.
        # Same log curve, mirrored — same maths as HF trending rank.
        anchor = ANCHORS.get(source, 24.0)
        if value <= 0:
            return 100.0
        return max(
            0.0,
            min(100.0, 100.0 - 50.0 * math.log10(value + 1) / math.log10(anchor + 1)),
        )
    anchor = ANCHORS.get(source)
    if anchor is None:
        # Unknown signal — neutral score. Shouldn't happen if enums match.
        return 50.0
    if value < 0:
        value = 0.0
    return min(100.0, 50.0 * math.log10(value + 1) / math.log10(anchor + 1))


def scaled_roc(now: float, then: float) -> float:
    """Map a 7-day rate-of-change to a 0–100 score.

    +0% growth = 50, +100% = 100, -50% = 0, capped at extremes.
    Guards against then=0 with a max() floor so brand-new signals
    don't blow up the formula.
    """
    base = max(then, 1.0)
    roc = (now - then) / base
    return max(0.0, min(100.0, 50.0 + 50.0 * roc))


# ----------------------------------------------------------- pillar maps

PILLAR_SOURCES_APPLICATION: dict[str, list[SignalSource]] = {
    "adoption": [
        SignalSource.GITHUB_STARS,
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.NPM_WEEKLY,
        SignalSource.PYPI_MONTHLY,
        SignalSource.MCP_REGISTRY_LISTED,
        SignalSource.STACKOVERFLOW_QUESTIONS_7D,
        SignalSource.PRODUCTHUNT_UPVOTES,
        SignalSource.DOCKER_PULLS_30D,
        SignalSource.CRATES_DOWNLOADS_90D,
    ],
    "quality": [
        SignalSource.BENCHMARK_SCORE,
        SignalSource.GITHUB_ISSUE_CLOSE_RATE_30D,
        SignalSource.GITHUB_FIRST_RESPONSE_HOURS_30D,
    ],
    "momentum": [
        SignalSource.GITHUB_STARS,
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.NPM_WEEKLY,
        SignalSource.PYPI_MONTHLY,
        SignalSource.HN_MENTIONS_7D,
        SignalSource.REDDIT_MENTIONS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.GITHUB_RELEASES_90D,
        SignalSource.GOOGLE_TRENDS_SCORE,
    ],
    "community": [
        SignalSource.GITHUB_CONTRIBUTORS,
        SignalSource.GITHUB_FORKS,
        SignalSource.HN_POINTS_7D,
        SignalSource.REDDIT_POINTS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.HF_LIKES,
        SignalSource.DISCORD_MEMBERS,
    ],
}

PILLAR_SOURCES_FOUNDATION_MODEL: dict[str, list[SignalSource]] = {
    "adoption": [
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.HN_MENTIONS_7D,
        SignalSource.REDDIT_MENTIONS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.GITHUB_STARS,
        SignalSource.GITHUB_MENTIONS_7D,
        SignalSource.WIKIPEDIA_VIEWS_30D,
        # OpenRouter token volume — best public proxy for "actual
        # production traffic" on FMs. Routinely diverges from
        # benchmark and HF download rankings.
        SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
    ],
    "quality": [SignalSource.BENCHMARK_SCORE],
    "momentum": [
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.HN_MENTIONS_7D,
        SignalSource.REDDIT_MENTIONS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.GITHUB_MENTIONS_7D,
        SignalSource.GOOGLE_TRENDS_SCORE,
        SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
    ],
    "community": [
        SignalSource.HF_LIKES,
        SignalSource.GITHUB_CONTRIBUTORS,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.REDDIT_POINTS_7D,
    ],
}


def _pillar_sources(entity_kind: str) -> dict[str, list[SignalSource]]:
    if entity_kind == "foundation_model":
        return PILLAR_SOURCES_FOUNDATION_MODEL
    return PILLAR_SOURCES_APPLICATION


# ----------------------------------------------------------- DB queries


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
    """Mean of latest benchmark scores across every benchmark this
    agent has results on. Each score is normalised against its
    benchmark's max_score so multiple benchmarks combine cleanly."""
    r = await session.execute(
        text(
            """
            WITH latest AS (
                SELECT br.benchmark_id, br.score, b.max_score,
                       ROW_NUMBER() OVER (
                           PARTITION BY br.benchmark_id
                           ORDER BY br.captured_at DESC
                       ) AS rn
                FROM benchmark_results br
                JOIN benchmarks b ON b.id = br.benchmark_id
                WHERE br.agent_id = :aid
            )
            SELECT
                AVG(
                    CASE
                        WHEN max_score IS NULL OR max_score <= 0 THEN score
                        ELSE score / max_score * 100
                    END
                )::float
            FROM latest WHERE rn = 1
            """
        ),
        {"aid": agent_id},
    )
    row = r.first()
    return float(row[0]) if row and row[0] is not None else None


async def _agent_kind(session: AsyncSession, agent_id: UUID) -> str:
    r = await session.execute(
        text("SELECT entity_kind FROM agents WHERE id = :id"),
        {"id": agent_id},
    )
    row = r.first()
    return (row[0] if row and row[0] else "application")


async def _agent_flags(session: AsyncSession, agent_id: UUID) -> dict | None:
    r = await session.execute(
        text("SELECT manipulation_flags FROM agents WHERE id = :id"),
        {"id": agent_id},
    )
    row = r.first()
    return row[0] if row and row[0] else None


def _excluded_sources(manipulation_flags: dict | None) -> set[SignalSource]:
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
    return max(0.1, 1.0 - 0.25 * n)


# ----------------------------------------------------------- pillar calc


async def _pillar_value(
    session: AsyncSession,
    agent_id: UUID,
    pillar: str,
    sources: list[SignalSource],
    excluded: set[SignalSource],
    is_momentum: bool,
) -> tuple[float | None, dict[str, Any]]:
    """Compute one pillar.

    Returns (score, inputs) where score is None if no contributing
    signal had a reading (the pillar is Unrated for this agent).
    inputs records each source we consulted with its raw value, the
    scaled contribution, and any reason it was skipped.
    """
    inputs: dict[str, Any] = {}
    contributions: list[float] = []

    for src in sources:
        if src in excluded:
            inputs[src.value] = {"status": "excluded"}
            continue

        if pillar == "quality" and src == SignalSource.BENCHMARK_SCORE:
            # Quality is special: the score lives in benchmark_results,
            # not the signals table.
            value = await _agent_benchmark_score(session, agent_id)
            if value is None:
                inputs[src.value] = {"status": "no_data"}
                continue
            contrib = scaled(value, src)
            inputs[src.value] = {
                "raw": value,
                "scaled": contrib,
                "anchor": "benchmark_max_score-normalized",
            }
            contributions.append(contrib)
            continue

        if is_momentum:
            now = await _latest_value(session, agent_id, src)
            if now is None:
                inputs[src.value] = {"status": "no_data"}
                continue
            then = await _value_at(session, agent_id, src, days_ago=7)
            if then is None:
                # Signal arrived in the last 7 days. Small positive bias.
                contrib = 60.0
                inputs[src.value] = {
                    "now": now,
                    "then": None,
                    "scaled": contrib,
                    "note": "newly arrived signal",
                }
            else:
                contrib = scaled_roc(now, then)
                inputs[src.value] = {
                    "now": now,
                    "then": then,
                    "roc": (now - then) / max(then, 1.0),
                    "scaled": contrib,
                }
            contributions.append(contrib)
            continue

        # Default path: latest reading scaled against its anchor.
        value = await _latest_value(session, agent_id, src)
        if value is None:
            inputs[src.value] = {"status": "no_data"}
            continue
        contrib = scaled(value, src)
        inputs[src.value] = {
            "raw": value,
            "scaled": contrib,
            "anchor": ANCHORS.get(src),
        }
        contributions.append(contrib)

    if not contributions:
        return None, inputs
    return sum(contributions) / len(contributions), inputs


# ----------------------------------------------------------- public


async def population_stats(session: AsyncSession) -> PopulationStats:
    """Compatibility shim. The new formula doesn't need population
    stats — every signal is scaled against an absolute anchor — but
    the recompute pipeline still passes a stats object around."""
    return PopulationStats()


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
    kind = await _agent_kind(session, agent_id)
    pillar_map = _pillar_sources(kind)

    adoption, adoption_in = await _pillar_value(
        session, agent_id, "adoption", pillar_map["adoption"], excluded, False
    )
    quality, quality_in = await _pillar_value(
        session, agent_id, "quality", pillar_map["quality"], excluded, False
    )
    momentum, momentum_in = await _pillar_value(
        session, agent_id, "momentum", pillar_map["momentum"], excluded, True
    )
    community, community_in = await _pillar_value(
        session, agent_id, "community", pillar_map["community"], excluded, False
    )

    pillars = PillarScores(
        adoption=adoption,
        quality=quality,
        momentum=momentum,
        community=community,
        manipulation_resistance=resistance,
        agent_score=None,
        inputs={
            "kind": kind,
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


def _headline(pillars: PillarScores, settings: Settings) -> float | None:
    """Weight-blended mean of non-null pillars. None if all are null."""
    weights = {
        "adoption": settings.weight_adoption,
        "quality": settings.weight_quality,
        "momentum": settings.weight_momentum,
        "community": settings.weight_community,
    }
    contributions: list[tuple[float, float]] = []
    for key in ("adoption", "quality", "momentum", "community"):
        value = getattr(pillars, key)
        if value is None:
            continue
        contributions.append((weights[key], value))
    if not contributions:
        return None
    total_w = sum(w for w, _ in contributions)
    if total_w <= 0:
        return None
    return sum(w * v for w, v in contributions) / total_w


# ----------------------------------------------------------- persist


async def persist_score(
    session: AsyncSession, agent_id: UUID, pillars: PillarScores
) -> UUID | None:
    """Insert a row in scores. Returns the new row id, or None if the
    agent is fully Unrated (no pillars + no headline)."""
    if pillars.agent_score is None:
        # Don't write null-headline rows; they'd pollute the
        # 24h-delta computations and the chart.
        return None
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


# ----------------------------------------------------------- batch


async def recompute_agents(
    session: AsyncSession,
    agent_ids: Iterable[UUID],
    redis_client: Any,
    settings: Settings | None = None,
) -> dict[str, int]:
    settings = settings or get_settings()
    pop = await population_stats(session)

    written = 0
    rank_changes = 0
    unrated = 0
    for aid in agent_ids:
        prior = await _prior_headline(session, aid)
        pillars = await compute_for_agent(session, aid, pop, settings)
        if pillars.agent_score is None:
            unrated += 1
            continue
        await persist_score(session, aid, pillars)
        written += 1

        if prior is None or _significant_change(prior, pillars.agent_score):
            rank_changes += 1
            await _emit_score_changed(session, redis_client, aid, prior, pillars)

    await session.commit()
    log.info(
        "scoring: recomputed %d (notable %d, unrated %d)",
        written, rank_changes, unrated,
    )
    return {
        "recomputed": written,
        "notable_changes": rank_changes,
        "unrated": unrated,
    }


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
    return abs(now - prior) >= 1.0


async def _emit_score_changed(
    session: AsyncSession,
    redis_client: Any,
    agent_id: UUID,
    prior: float | None,
    pillars: PillarScores,
) -> None:
    slug_row = await session.execute(
        text("SELECT slug FROM agents WHERE id = :id"), {"id": agent_id}
    )
    slug = slug_row.scalar_one_or_none()

    payload = {
        "kind": "score_changed",
        "agent_id": str(agent_id),
        "agent_slug": slug,
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
    body = json.dumps(payload)
    try:
        await redis_client.publish("events.global", body)
        if slug:
            await redis_client.publish(f"events.agent.{slug}", body)
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (score_changed) failed: %s", e)


async def all_admitted_agent_ids(session: AsyncSession) -> list[UUID]:
    r = await session.execute(
        text("SELECT id FROM agents WHERE eligibility_status = 'admitted'")
    )
    return [row[0] for row in r]
