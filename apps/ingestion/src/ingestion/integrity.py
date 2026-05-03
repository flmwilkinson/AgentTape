"""Manipulation detection.

Three rules from the spec:

1. ``star_spike_no_contrib_diversity`` —
   GitHub stars jumped >10x in 24h while the contributor count is small.
   Classic farmed-stars pattern: a small repo with a dozen contributors
   doesn't organically pull tens of thousands of new stargazers in a day.

2. ``hf_surge_no_github`` —
   HF downloads surged but no commits, no fork count change, no star
   change on the linked GitHub repo over the same window. Could be an
   honest cache-miss flood, but more often it's bot-driven.

3. ``coordinated_hn_posting`` —
   ``hn_mentions_7d`` jumped sharply in the last fast-tier window. We
   don't have per-poster identity in our store (that lives in the
   discovery payload), so this rule is a leading indicator: it flags
   for review rather than concluding fraud.

Flags accumulate on ``agents.manipulation_flags`` as a JSON object keyed
by rule name; each entry has the captured-at, the values that triggered
it, and a one-line ``reason``. ``agent_flagged`` events go to the
events table and Redis so the realtime UI can show a badge instantly.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import Settings
from ingestion.enums import SignalSource

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Flag:
    rule: str
    reason: str
    details: dict[str, Any]


# ---------------------------------------------------------------- rules


def detect_star_spike_without_contrib_diversity(
    *,
    stars_now: float,
    stars_24h_ago: float | None,
    contributor_count: float | None,
    settings: Settings,
) -> Flag | None:
    if stars_24h_ago is None or stars_24h_ago == 0:
        return None
    multiplier = stars_now / stars_24h_ago
    if multiplier < settings.star_spike_24h_multiplier:
        return None
    if (contributor_count or 0) >= settings.min_contributors_for_organic_spike:
        return None
    return Flag(
        rule="star_spike_no_contrib_diversity",
        reason=(
            f"stars {stars_24h_ago:.0f} -> {stars_now:.0f} ({multiplier:.1f}x) "
            f"with only {contributor_count or 0:.0f} contributors"
        ),
        details={
            "stars_24h_ago": stars_24h_ago,
            "stars_now": stars_now,
            "multiplier": multiplier,
            "contributor_count": contributor_count,
        },
    )


def detect_hf_surge_without_github(
    *,
    hf_downloads_now: float,
    hf_downloads_24h_ago: float | None,
    stars_now: float | None,
    stars_24h_ago: float | None,
    commits_7d: float | None,
    settings: Settings,
) -> Flag | None:
    if hf_downloads_24h_ago is None or hf_downloads_24h_ago == 0:
        return None
    hf_mult = hf_downloads_now / hf_downloads_24h_ago
    if hf_mult < settings.spike_multiplier:
        return None
    star_delta = (
        (stars_now - stars_24h_ago)
        if (stars_now is not None and stars_24h_ago is not None)
        else None
    )
    # Star growth in line with HF surge would be normal coordinated launch.
    # Bot floods are characterized by HF surge AND a flat GitHub side.
    if star_delta is not None and stars_24h_ago and (star_delta / stars_24h_ago) >= 0.10:
        return None
    if (commits_7d or 0) > 0:
        # Active development could explain a real download surge.
        return None
    return Flag(
        rule="hf_surge_no_github",
        reason=(
            f"hf downloads {hf_downloads_24h_ago:.0f} -> {hf_downloads_now:.0f} "
            f"({hf_mult:.1f}x) with no github activity"
        ),
        details={
            "hf_downloads_24h_ago": hf_downloads_24h_ago,
            "hf_downloads_now": hf_downloads_now,
            "stars_now": stars_now,
            "stars_24h_ago": stars_24h_ago,
            "commits_7d": commits_7d,
        },
    )


def detect_coordinated_hn_posting(
    *,
    hn_mentions_now: float,
    hn_mentions_recent: list[float],
    settings: Settings,
) -> Flag | None:
    """Sharp jump versus the rolling baseline of recent fast-tier ticks."""
    if not hn_mentions_recent:
        return None
    # Use the median of the last few readings as the baseline; means are
    # too easily perturbed by the very spike we're trying to detect.
    base = sorted(hn_mentions_recent)[len(hn_mentions_recent) // 2]
    if base <= 1:
        return None
    if hn_mentions_now < base * settings.spike_multiplier * 2:
        return None
    return Flag(
        rule="coordinated_hn_posting",
        reason=(
            f"hn mentions baseline ~{base:.0f} -> {hn_mentions_now:.0f} "
            f"({hn_mentions_now / base:.1f}x in one window)"
        ),
        details={
            "baseline": base,
            "now": hn_mentions_now,
            "history": hn_mentions_recent,
        },
    )


# ---------------------------------------------------------------- driver


async def run_integrity_checks(
    session: AsyncSession,
    redis_client: Any,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Re-evaluate manipulation rules over every admitted agent.

    Cheap to run on every medium-tier tick: each rule is one query to
    grab the most recent and 24h-ago values from the partitioned
    ``signals`` table, both of which hit the (agent_id, source,
    captured_at DESC) index.
    """
    settings = settings or Settings()
    rows = (
        await session.execute(
            text("SELECT id FROM agents WHERE eligibility_status = 'admitted'")
        )
    ).all()

    flagged = 0
    for (agent_id,) in rows:
        flags = await _evaluate_for_agent(session, agent_id, settings)
        if flags:
            await _persist_flags(session, redis_client, agent_id, flags)
            flagged += 1
    await session.commit()
    log.info("integrity: %d agents flagged of %d admitted", flagged, len(rows))
    return {"agents_checked": len(rows), "flagged": flagged}


async def _evaluate_for_agent(
    session: AsyncSession, agent_id: UUID, settings: Settings
) -> list[Flag]:
    stars_now = await _latest(session, agent_id, SignalSource.GITHUB_STARS)
    stars_24h_ago = await _value_at(
        session, agent_id, SignalSource.GITHUB_STARS, hours=24
    )
    contributors = await _latest(session, agent_id, SignalSource.GITHUB_CONTRIBUTORS)
    commits_7d = await _latest(session, agent_id, SignalSource.GITHUB_COMMITS_7D)
    hf_now = await _latest(session, agent_id, SignalSource.HF_DOWNLOADS_30D)
    hf_24h_ago = await _value_at(
        session, agent_id, SignalSource.HF_DOWNLOADS_30D, hours=24
    )
    hn_now = await _latest(session, agent_id, SignalSource.HN_MENTIONS_7D)
    hn_recent = await _recent_values(
        session, agent_id, SignalSource.HN_MENTIONS_7D, limit=10
    )

    flags: list[Flag] = []
    if stars_now is not None:
        f1 = detect_star_spike_without_contrib_diversity(
            stars_now=stars_now,
            stars_24h_ago=stars_24h_ago,
            contributor_count=contributors,
            settings=settings,
        )
        if f1:
            flags.append(f1)
    if hf_now is not None:
        f2 = detect_hf_surge_without_github(
            hf_downloads_now=hf_now,
            hf_downloads_24h_ago=hf_24h_ago,
            stars_now=stars_now,
            stars_24h_ago=stars_24h_ago,
            commits_7d=commits_7d,
            settings=settings,
        )
        if f2:
            flags.append(f2)
    if hn_now is not None:
        f3 = detect_coordinated_hn_posting(
            hn_mentions_now=hn_now,
            hn_mentions_recent=hn_recent,
            settings=settings,
        )
        if f3:
            flags.append(f3)
    return flags


# ---------------------------------------------------------------- queries


async def _latest(
    session: AsyncSession, agent_id: UUID, source: SignalSource
) -> float | None:
    r = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid AND source = CAST(:src AS signal_source)
            ORDER BY captured_at DESC
            LIMIT 1
            """
        ),
        {"aid": agent_id, "src": source.value},
    )
    row = r.first()
    return float(row[0]) if row else None


async def _value_at(
    session: AsyncSession, agent_id: UUID, source: SignalSource, hours: int
) -> float | None:
    """Closest reading at-or-before now-hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    r = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid
              AND source = CAST(:src AS signal_source)
              AND captured_at <= :cutoff
            ORDER BY captured_at DESC
            LIMIT 1
            """
        ),
        {"aid": agent_id, "src": source.value, "cutoff": cutoff},
    )
    row = r.first()
    return float(row[0]) if row else None


async def _recent_values(
    session: AsyncSession,
    agent_id: UUID,
    source: SignalSource,
    *,
    limit: int,
) -> list[float]:
    r = await session.execute(
        text(
            """
            SELECT value FROM signals
            WHERE agent_id = :aid AND source = CAST(:src AS signal_source)
            ORDER BY captured_at DESC
            LIMIT :n
            """
        ),
        {"aid": agent_id, "src": source.value, "n": limit},
    )
    return [float(row[0]) for row in r]


# ---------------------------------------------------------------- persist


async def _persist_flags(
    session: AsyncSession,
    redis_client: Any,
    agent_id: UUID,
    flags: list[Flag],
) -> None:
    flag_obj: dict[str, Any] = {
        f.rule: {
            "reason": f.reason,
            "captured_at": datetime.now(UTC).isoformat(),
            "details": f.details,
        }
        for f in flags
    }
    await session.execute(
        text(
            """
            UPDATE agents
            SET manipulation_flags = COALESCE(manipulation_flags, CAST('{}' AS jsonb))
                                     || CAST(:flags AS jsonb)
            WHERE id = :id
            """
        ),
        {"id": agent_id, "flags": json.dumps(flag_obj)},
    )
    # Look up the agent slug so we can address events.agent.<slug>.
    slug_row = await session.execute(
        text("SELECT slug FROM agents WHERE id = :id"), {"id": agent_id}
    )
    slug = slug_row.scalar_one_or_none()

    payload = {
        "kind": "agent_flagged",
        "agent_id": str(agent_id),
        "agent_slug": slug,
        "flags": flag_obj,
    }
    await session.execute(
        text(
            """
            INSERT INTO events (id, kind, agent_id, payload)
            VALUES (gen_random_uuid(), CAST('agent_flagged' AS event_kind), :id, CAST(:p AS jsonb))
            """
        ),
        {"id": agent_id, "p": json.dumps(payload)},
    )
    body = json.dumps(payload)
    try:
        await redis_client.publish("events.global", body)
        if slug:
            await redis_client.publish(f"events.agent.{slug}", body)
    except Exception as e:  # noqa: BLE001
        log.warning("redis publish (flag) failed: %s", e)
