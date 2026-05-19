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
    # Migration 0012. FM-only 5th pillar — cost + speed. Always None
    # for applications (the pillar map's efficiency list is empty so
    # ``_pillar_value`` returns no contributions). Stored in scores
    # alongside the other pillars.
    efficiency: float | None
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
    # Cumulative repos calling a foundation model. 100 distinct repos
    # = score 50 — that's "real ecosystem traction, not a one-off".
    # Top FMs (Claude, GPT) clear several thousand and so peg at 100.
    SignalSource.GITHUB_REPOS_USING_MODEL: 100,
    # Tech-news mentions in the last 30 days. Producer is GDELT
    # (~150k outlets) with the curated RSS list as a fallback.
    # Anchor at 30 because the GDELT corpus is much wider than the
    # old RSS-only signal — saturating at 250 (the API ceiling)
    # keeps the truly famous flagships pegged near 100, and
    # 30 articles in a month is a fair "household name" threshold.
    SignalSource.NEWS_MENTIONS_30D: 30,
    # Mastodon mentions across a few large instances. Sister of
    # Bluesky — anchor at 5 (lower than Bluesky's 10) because
    # Mastodon's federated public-search returns less than Bluesky's
    # global firehose for the same agent.
    SignalSource.MASTODON_MENTIONS_7D: 5,
    # Migration 0012 — FM Efficiency signals.
    # Blended price per million tokens. Inverse-anchored via the
    # special case in scaled(): cheaper = higher. $5/M = score 50
    # (mid-tier flagships like Claude Sonnet/GPT-4o land here);
    # $0.50/M = score ~80 (commodity models); $25+/M = score ~25.
    SignalSource.OPENROUTER_PRICE_BLENDED: 5,
    # Output tokens per second — higher = better. Anchor at 50
    # tok/s = score 50. A frontier model serving at ~150 tok/s
    # lands ~75; a slow cloud model at 20 tok/s lands ~30.
    SignalSource.OUTPUT_TOKENS_PER_SECOND: 50,
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
    if source == SignalSource.OPENROUTER_PRICE_BLENDED:
        # Inverted: cheaper = higher. $0/M ≈ 100, $5/M = 50, $50/M ≈ 0.
        # Same mirrored log curve as github_first_response_hours.
        anchor = ANCHORS.get(source, 5.0)
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
        # Mainstream tech-press coverage. Captures household-name
        # apps the social signals undercount (e.g. enterprise tools
        # that aren't on HN much).
        SignalSource.NEWS_MENTIONS_30D,
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
        # Mastodon mirrors Bluesky on the federated side — both
        # appear in adoption (level) and momentum (rate), neither in
        # community (would triple-count the same conversation).
        SignalSource.MASTODON_MENTIONS_7D,
        SignalSource.GITHUB_RELEASES_90D,
        SignalSource.GOOGLE_TRENDS_SCORE,
    ],
    "community": [
        SignalSource.GITHUB_CONTRIBUTORS,
        SignalSource.GITHUB_FORKS,
        SignalSource.HN_POINTS_7D,
        SignalSource.REDDIT_POINTS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        # Mastodon mirrors Bluesky's pattern — community for apps
        # captures contributor + commentator engagement together.
        SignalSource.MASTODON_MENTIONS_7D,
        SignalSource.HF_LIKES,
        SignalSource.DISCORD_MEMBERS,
    ],
    # Applications don't have a meaningful Efficiency signal — they
    # run on the user's hardware and don't carry per-token pricing
    # like hosted FMs do. Empty list keeps the structure parallel
    # so compute_for_agent doesn't need entity-kind branching, and
    # apps stay Unrated on Efficiency rather than fake-zero.
    "efficiency": [],
}

PILLAR_SOURCES_FOUNDATION_MODEL: dict[str, list[SignalSource]] = {
    "adoption": [
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.HN_MENTIONS_7D,
        SignalSource.REDDIT_MENTIONS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.MASTODON_MENTIONS_7D,
        SignalSource.GITHUB_STARS,
        SignalSource.GITHUB_MENTIONS_7D,
        SignalSource.WIKIPEDIA_VIEWS_30D,
        # OpenRouter token volume is the best public proxy for "actual
        # production traffic" on FMs. Routinely diverges from
        # benchmark and HF download rankings.
        SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
        # Number of GitHub repos calling this model. The most direct
        # public answer to "how widely is this model adopted by app
        # developers". Lives in adoption rather than community
        # because the user-facing question is "how popular is the
        # model" — community matters but ecosystem reach matters more.
        SignalSource.GITHUB_REPOS_USING_MODEL,
        # Tech-press coverage. The household-name signal the GPT/
        # Claude/Gemini flagships would otherwise undercount on
        # Hacker News alone.
        SignalSource.NEWS_MENTIONS_30D,
    ],
    "quality": [
        # Quality is now BENCHMARK_SCORE only for foundation models.
        # ARXIV_CITATIONS was here previously on the theory that
        # peer-reviewed citations stand in for benchmark coverage on
        # newly-released flagships before leaderboards catch up. In
        # practice it harmed the signal it was meant to help: closed
        # flagships (Claude, GPT) don't have linked arxiv papers,
        # ARXIV_CITATIONS scaled to 0, and the mean dragged
        # benchmark-based Quality down to half. Visible in prod as
        # Claude Opus 4.7 at quality=43.7 despite SWE-bench=87.6 etc.
        # Citations moved to Momentum below — they're an academic-
        # adoption rate signal, not a capability signal.
        SignalSource.BENCHMARK_SCORE,
    ],
    "momentum": [
        SignalSource.HF_DOWNLOADS_30D,
        SignalSource.HN_MENTIONS_7D,
        SignalSource.REDDIT_MENTIONS_7D,
        SignalSource.BLUESKY_MENTIONS_7D,
        SignalSource.MASTODON_MENTIONS_7D,
        SignalSource.GITHUB_MENTIONS_7D,
        SignalSource.GOOGLE_TRENDS_SCORE,
        SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
        # Academic mentions over time — newer papers citing this
        # model are a credible "still relevant" signal. The momentum
        # pillar treats it as a 7-day rate via scaled_roc, so a
        # model with a flat citation count doesn't get penalised
        # — only models gaining (or losing) academic mindshare move.
        SignalSource.ARXIV_CITATIONS,
    ],
    "community": [
        # Note: BLUESKY_MENTIONS_7D, MASTODON_MENTIONS_7D and
        # GITHUB_REPOS_USING_MODEL were removed here — the social
        # signals already feed Adoption + Momentum, repos-using-
        # model feeds Adoption. Each signal lives in exactly one
        # pillar to keep the mean-of-scaled-signals math clean.
        SignalSource.HF_LIKES,
        SignalSource.GITHUB_CONTRIBUTORS,
        SignalSource.REDDIT_POINTS_7D,
    ],
    "efficiency": [
        # FM-only fifth pillar. Captures production-fit:
        # how cheap and how fast does this model serve at scale?
        # Both signals sourced from the Artificial Analysis API
        # (canonical reference for LLM economics).
        # Price uses an inverse log anchor in scaled() — cheaper
        # scores higher. Tokens/sec uses the standard log curve —
        # faster scores higher. Both are independent of capability,
        # which is why this is a separate pillar rather than
        # rolled into Quality.
        SignalSource.OPENROUTER_PRICE_BLENDED,
        SignalSource.OUTPUT_TOKENS_PER_SECOND,
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


MIN_BENCHMARK_COVERAGE = 3
"""How many distinct benchmarks must an agent appear on before we
assign a Quality score from them.

Below this floor the agent stays Unrated on Quality (rather than
getting a misleading score from a single source). Verified in prod:
``google-gemini-3-flash-preview`` had Quality=98.1 from one lmarena
Elo row, which falsely placed it above Claude Opus 4.7 and GPT-5.5
on the headline ranking. The floor of 3 forces a minimum of three
canonical benchmarks (lmarena, swe-bench-verified, mmlu-pro is a
typical cohort that most frontier models clear) before Quality is
trusted as a comparable signal."""


async def _agent_benchmark_score(
    session: AsyncSession, agent_id: UUID
) -> float | None:
    """Mean percentile rank across the agent's benchmark coverage.

    For each benchmark the agent has been scored on, computes its
    percentile rank among the population of agents on that
    benchmark. Returns the mean percentile across the agent's
    benchmarks.

    This replaces a prior mean-of-normalised-scores formula which
    produced wrong head-to-head rankings whenever models had
    different benchmark coverage. The pathological case observed
    in prod: GPT-5.5 strictly beat GPT-5.1 on all 5 of their shared
    benchmarks (aa-coding, aa-intelligence, gpqa-diamond, ifbench,
    scicode), but GPT-5.1 outranked it because GPT-5.1 had 5 extra
    benchmarks (some inflated by the AA fractional bug, some
    genuinely easy like math/aime where most models score high).

    Percentile rank fixes this:

    * Coverage-robust — what matters is consistently beating peers
      on the benchmarks tested, not absolute score on a longer-or-
      shorter benchmark list.
    * Head-to-head consistent — if A beats B on every shared
      benchmark, A's mean percentile is >= B's.
    * Difficulty-adjusted — 60 on a hard benchmark (median 40) is
      worth more than 60 on a saturated one (median 90), because
      population-relative position is what the percentile captures.

    Coverage gate: same ``MIN_BENCHMARK_COVERAGE`` floor. Below it
    the agent stays Unrated regardless of percentile (a model with
    one 99th-percentile benchmark is still under-measured).
    """
    r = await session.execute(
        text(
            """
            WITH latest_per_pair AS (
                -- Latest score per (agent, benchmark). DISTINCT ON
                -- gives us one row per pair, keyed by the most recent
                -- captured_at within that pair.
                SELECT DISTINCT ON (br.agent_id, br.benchmark_id)
                    br.agent_id,
                    br.benchmark_id,
                    br.score
                FROM benchmark_results br
                ORDER BY br.agent_id, br.benchmark_id, br.captured_at DESC
            ),
            percentiles AS (
                -- Rank each (agent, benchmark) row within its benchmark's
                -- population. PERCENT_RANK gives 0 for the lowest score
                -- and 1 for the highest; multiply by 100 to surface as a
                -- 0-100 quality contribution.
                SELECT
                    agent_id,
                    100.0 * PERCENT_RANK() OVER (
                        PARTITION BY benchmark_id ORDER BY score
                    ) AS pct
                FROM latest_per_pair
            )
            SELECT
                count(*)::int AS n,
                AVG(pct)::float AS mean_pct
            FROM percentiles
            WHERE agent_id = :aid
            """
        ),
        {"aid": agent_id},
    )
    row = r.first()
    if row is None:
        return None
    n, mean_pct = row[0], row[1]
    if n is None or mean_pct is None or n < MIN_BENCHMARK_COVERAGE:
        return None
    return float(mean_pct)


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
    # FM-only 5th pillar — empty list for applications returns None
    # which is the correct Unrated state, not a fake zero.
    efficiency, efficiency_in = await _pillar_value(
        session,
        agent_id,
        "efficiency",
        pillar_map.get("efficiency", []),
        excluded,
        False,
    )

    pillars = PillarScores(
        adoption=adoption,
        quality=quality,
        momentum=momentum,
        community=community,
        efficiency=efficiency,
        manipulation_resistance=resistance,
        agent_score=None,
        inputs={
            "kind": kind,
            "adoption": adoption_in,
            "quality": quality_in,
            "momentum": momentum_in,
            "community": community_in,
            "efficiency": efficiency_in,
            "excluded": [s.value for s in excluded],
            "manipulation_flags": list(flags or {}),
        },
    )
    pillars.agent_score = _headline(pillars, settings)
    return pillars


def _headline(pillars: PillarScores, settings: Settings) -> float | None:
    """Flat weighted sum. Missing pillar contributes zero.

    The "missing = 0" rule does the work: a pillar with no signals
    contributes nothing, so the maximum any one pillar can buy is its
    own weight. A 1-pillar agent with Adoption at 100 caps at 40 (its
    weight × 100). A 4-pillar agent rated 70 across the board reaches
    70. More data structurally beats less data — no separate
    multiplier needed.

    Weights are entity-kind specific (see config.Settings):

        Application    : 0.40 adoption + 0.20 quality
                       + 0.10 momentum + 0.30 community
        Foundation mdl : 0.25 adoption + 0.35 quality + 0.20 efficiency
                       + 0.10 momentum + 0.10 community

    Both sets sum to 1.0 so headlines stay on the 0-100 scale.
    Applications don't have an efficiency pillar (FM-only) — its
    weight is 0 so the missing pillar contributes nothing.

    Returns None only when *every* pillar is null — those agents stay
    unranked and don't pollute the leaderboard with synthetic zeros.
    """
    kind = pillars.inputs.get("kind", "application")
    if kind == "foundation_model":
        weights = {
            "adoption": settings.weight_fm_adoption,
            "quality": settings.weight_fm_quality,
            "momentum": settings.weight_fm_momentum,
            "community": settings.weight_fm_community,
            "efficiency": settings.weight_fm_efficiency,
        }
    else:
        weights = {
            "adoption": settings.weight_app_adoption,
            "quality": settings.weight_app_quality,
            "momentum": settings.weight_app_momentum,
            "community": settings.weight_app_community,
            # Applications: efficiency weight=0 so any future signals
            # in the bucket wouldn't accidentally shift the app score.
            "efficiency": 0.0,
        }
    if all(getattr(pillars, k) is None for k in weights):
        return None
    total = 0.0
    for key, w in weights.items():
        value = getattr(pillars, key)
        if value is None:
            continue
        total += w * value
    return total


# ----------------------------------------------------------- persist


async def persist_score(
    session: AsyncSession, agent_id: UUID, pillars: PillarScores
) -> UUID | None:
    """Insert a row in scores, deduped against the most-recent prior.

    Returns the new row id, ``None`` if the agent is fully Unrated, or
    ``None`` if the new computation matches the most recent stored
    score (no point writing a duplicate).

    Dedupe is the whole reason storage stays bounded — without it
    every heartbeat recompute writes a row whether or not anything
    changed, which fills the database in days. The tolerance (0.01)
    suppresses float-noise differences while still recording any
    real movement the chart should show.
    """
    if pillars.agent_score is None:
        # Don't write null-headline rows; they'd pollute the
        # 24h-delta computations and the chart.
        return None

    # Look at the most-recent row in flight for this agent. Plain
    # LIMIT 1 (no OFFSET) — we want the actual current state, not
    # the row-before-the-current-one that _prior_headline returns.
    prev = (
        await session.execute(
            text(
                """
                SELECT agent_score, adoption, quality, momentum, community, efficiency
                FROM scores
                WHERE agent_id = :aid
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {"aid": agent_id},
        )
    ).first()
    if prev is not None and _scores_equal(prev, pillars):
        # Unchanged — skip the INSERT. The previous row remains the
        # current state, so reads aren't affected.
        return None

    r = await session.execute(
        text(
            """
            INSERT INTO scores (
                id, agent_id, computed_at,
                agent_score, adoption, quality, momentum, community, efficiency,
                manipulation_resistance
            ) VALUES (
                gen_random_uuid(), :aid, now(),
                :a, :ad, :q, :m, :c, :eff, :mr
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
            "eff": pillars.efficiency,
            "mr": pillars.manipulation_resistance,
        },
    )
    return r.scalar_one()


def _scores_equal(prev, pillars: PillarScores) -> bool:
    """Compare a stored score row to a freshly-computed PillarScores.

    Float-noise tolerance: anything within 0.01 of the prior on every
    pillar AND on the headline counts as unchanged. The chart resolution
    is one decimal place — a sub-0.01 movement is meaningless to a
    reader and isn't worth a row.
    """
    def eq(a: float | None, b: float | None) -> bool:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) < 0.01

    return (
        eq(prev.agent_score, pillars.agent_score)
        and eq(prev.adoption, pillars.adoption)
        and eq(prev.quality, pillars.quality)
        and eq(prev.momentum, pillars.momentum)
        and eq(prev.community, pillars.community)
        and eq(prev.efficiency, pillars.efficiency)
    )


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
    deduped = 0
    rank_changes = 0
    unrated = 0
    for aid in agent_ids:
        prior = await _prior_headline(session, aid)
        pillars = await compute_for_agent(session, aid, pop, settings)
        if pillars.agent_score is None:
            unrated += 1
            continue
        row_id = await persist_score(session, aid, pillars)
        if row_id is None:
            # Dedupe — score matched the most-recent stored row.
            # No new row, no event. Move on.
            deduped += 1
            continue
        written += 1

        if prior is None or _significant_change(prior, pillars.agent_score):
            rank_changes += 1
            await _emit_score_changed(session, redis_client, aid, prior, pillars)

    await session.commit()
    log.info(
        "scoring: recomputed %d (notable %d, deduped %d, unrated %d)",
        written, rank_changes, deduped, unrated,
    )
    return {
        "recomputed": written,
        "notable_changes": rank_changes,
        "deduped": deduped,
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
