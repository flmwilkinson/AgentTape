"""Artificial Analysis API — the canonical FM benchmark/cost/speed source.

Solves three problems at once that the scraping path couldn't:

1. **Coverage on newest flagships.** Anthropic / OpenAI / Google
   publish scores in prose on Vellum / MindStudio / PADISO blogs.
   We can't scrape prose. Artificial Analysis ingests those scores
   into structured JSON and republishes via their public API. Opus
   4.7, GPT-5.5, Gemini 3.1 Pro all appear with every canonical
   Intelligence Index component populated.

2. **Cost + Speed signals.** The same response carries
   ``price_1m_input_tokens``, ``price_1m_output_tokens``, and
   ``median_output_tokens_per_second`` — which feed the new
   Efficiency pillar without needing a second integration.

3. **Stable identifiers.** Each model has ``id``, ``slug`` and
   ``model_creator.slug``. We build a canonical match key
   ``{creator_slug}-{model_slug}`` that lines up exactly with our
   agent slugs (e.g. ``anthropic-claude-opus-4-7``), so the matching
   nightmare with leaderboard name variants is gone.

Output split:

- **Per-benchmark scores** (gpqa, mmlu_pro, math_500, aime,
  livecodebench, hle, terminal_bench_hard, scicode, etc.) →
  ``benchmark_results`` rows under existing benchmark slugs where
  they map cleanly, new slugs for AA-only entries.

- **Intelligence Index composite** → its own benchmark row
  ``aa-intelligence-index`` so Quality picks it up alongside other
  benchmarks. Doesn't replace lmarena / swe-bench — joins them.

- **Cost** is no longer written here: ``OPENROUTER_PRICE_BLENDED``
  now comes from OpenRouter directly (``openrouter_pricing.py``),
  which covers every listed model.

- **Speed** → ``OUTPUT_TOKENS_PER_SECOND`` signal.

Attribution required per AA's terms: methodology page links to
artificialanalysis.ai/methodology/intelligence-benchmarking.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


AA_API = "https://artificialanalysis.ai/api/v2/data/llms/models"


# AA response field → (our ``benchmarks.name`` slug, category). When
# the slug already exists (e.g. gpqa-diamond, mmlu-pro), AA's value
# overwrites on the next tick — AA's coverage is generally more
# comprehensive than what we scrape directly.
#
# Field names track the live v2 payload. AA renamed several of them
# (humanitys_last_exam → hle, terminal_bench_hard → terminalbench_hard,
# tau2_bench_telecom → tau2, aa_lcr → lcr), and the stale names read
# None silently — HLE alone is reported for ~630 models.
BENCHMARK_FIELD_MAP: dict[str, tuple[str, str]] = {
    "evaluations.artificial_analysis_intelligence_index": (
        "aa-intelligence-index", "reasoning",
    ),
    "evaluations.artificial_analysis_coding_index": (
        "aa-coding-index", "coding",
    ),
    "evaluations.artificial_analysis_math_index": (
        "aa-math-index", "math",
    ),
    "evaluations.mmlu_pro": ("mmlu-pro", "reasoning"),
    "evaluations.gpqa": ("gpqa-diamond", "reasoning"),
    "evaluations.math_500": ("math-500", "math"),
    "evaluations.aime": ("aime-2024", "math"),
    "evaluations.aime_25": ("aime-2025", "math"),
    "evaluations.livecodebench": ("livecodebench", "coding"),
    "evaluations.scicode": ("scicode", "reasoning"),
    "evaluations.hle": ("hle", "reasoning"),
    "evaluations.terminalbench_hard": ("terminal-bench-hard", "agentic"),
    "evaluations.terminalbench_v2_1": ("terminal-bench-2-1", "agentic"),
    "evaluations.tau2": ("tau2-bench-telecom", "agentic"),
    "evaluations.tau_banking": ("tau-banking", "agentic"),
    "evaluations.ifbench": ("ifbench", "reasoning"),
    "evaluations.lcr": ("aa-lcr", "reasoning"),
}

# Composite indices are published on 0–100; every other evaluation is
# a 0–1 fraction. Explicit per field — the old "≤ 1.5 means fraction"
# guess turned a low index score (e.g. coding index 1.0) into 100.
_PERCENT_SCALE_FIELDS = {
    "evaluations.artificial_analysis_intelligence_index",
    "evaluations.artificial_analysis_coding_index",
    "evaluations.artificial_analysis_math_index",
}


def _to_percent(field: str, value: Any) -> float | None:
    """Normalise one AA evaluation to 0–100, or None to skip it.

    Zero is skipped: AA reports 0 for evaluations it hasn't run on a
    model yet, and writing it would rank the model last.
    """
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score <= 0:
        return None
    if field not in _PERCENT_SCALE_FIELDS:
        # Cap at 100: pass@k style fields can exceed 1.0.
        score = min(score * 100.0, 100.0)
    if score > 100.0:
        return None
    # Columns are numeric(20, 6); round so the dedupe comparison
    # against the stored prior sees 96.3, not 96.30000000000001.
    return round(score, 6)


# AA creator slug → our agent-slug prefix(es). Our FM slugs come from
# OpenRouter display names ("Z.ai: GLM 5" → z-ai-glm-5), which name
# several creators differently from AA.
_CREATOR_ALIASES: dict[str, tuple[str, ...]] = {
    "alibaba": ("qwen",),
    "zai": ("z-ai",),
    "kimi": ("moonshotai",),
    "aws": ("amazon",),
    "nous-research": ("nous",),
    "ai2": ("allenai",),
    "bytedance_seed": ("bytedance-seed",),
    "xai": ("xai", "spacexai"),
    "mistral": ("mistral", "mistralai"),
}

# AA lists reasoning-effort variants as separate models ("-xhigh",
# "-high", ...). Strongest first: when AA has no un-suffixed entry for
# a model, the strongest effort stands in for it.
_EFFORTS = ("max", "xhigh", "high", "medium", "low", "minimal")
_EFFORT_SUFFIX = re.compile(r"-(" + "|".join(_EFFORTS) + r")$")


def match_models(
    models: list[dict[str, Any]], agent_slugs: dict[str, UUID]
) -> dict[UUID, dict[str, Any]]:
    """Map each matchable agent to the AA model record that describes it.

    Tries ``{creator}-{slug}`` with creator aliases, then the same with
    ``-preview`` appended (OpenRouter keeps "Preview" in names AA drops).
    An effort-suffixed AA entry is used only when AA has no plain entry
    for that model, and the strongest effort wins.
    """
    plain_keys = {
        f"{(m.get('model_creator') or {}).get('slug')}-{m.get('slug')}".lower()
        for m in models
        if isinstance(m, dict)
    }
    best: dict[UUID, tuple[int, dict[str, Any]]] = {}
    for m in models:
        if not isinstance(m, dict):
            continue
        creator = ((m.get("model_creator") or {}).get("slug") or "").lower()
        model_slug = (m.get("slug") or "").lower()
        if not (creator and model_slug):
            continue
        rank = -1  # exact entries beat any effort variant
        effort = _EFFORT_SUFFIX.search(model_slug)
        if effort:
            base = model_slug[: effort.start()]
            if f"{creator}-{base}" in plain_keys:
                continue  # AA has the plain model; ignore its variants
            model_slug = base
            rank = _EFFORTS.index(effort.group(1))
        for prefix in _CREATOR_ALIASES.get(creator, (creator,)):
            for key in (f"{prefix}-{model_slug}", f"{prefix}-{model_slug}-preview"):
                aid = agent_slugs.get(key)
                if aid is None:
                    continue
                if aid not in best or rank < best[aid][0]:
                    best[aid] = (rank, m)
                break
    return {aid: m for aid, (_, m) in best.items()}


class ArtificialAnalysisIngestor(Ingestor):
    """Pulls AA's per-model JSON, fans out to benchmark_results +
    Efficiency signals.

    Overrides ``run`` because we write to two tables (signals and
    benchmark_results) like ``FMLeaderboardsIngestor`` does. Same
    upsert + dedupe pattern.
    """

    name: ClassVar[str] = "artificial_analysis"
    source: ClassVar[SignalSource] = SignalSource.BENCHMARK_SCORE
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # Not used — we override run() to fan out across signals +
        # benchmark_results in one pass.
        return []

    async def run(
        self,
        session: AsyncSession,
        agents: list[AgentRow],
        redis_client: Any,
    ) -> dict[str, int]:
        api_key = self.settings.artificial_analysis_api_key
        if not api_key:
            log.info("artificial_analysis: no ARTIFICIAL_ANALYSIS_API_KEY, skipping")
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}

        try:
            r = await self._http.get(
                AA_API, headers={"x-api-key": api_key}
            )
        except Exception as e:  # noqa: BLE001
            log.warning("artificial_analysis fetch failed: %s", e)
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}
        if r.status_code != 200:
            log.warning("artificial_analysis returned %d", r.status_code)
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}

        try:
            data = r.json()
        except (ValueError, json.JSONDecodeError):
            log.warning("artificial_analysis: non-JSON response")
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}

        models = data.get("data") if isinstance(data, dict) else data
        if not isinstance(models, list):
            log.warning("artificial_analysis: unexpected payload shape")
            return {"fetched": 0, "written": 0, "spiked": 0, "changed": 0}

        captured = datetime.now(UTC)
        bench_ids: dict[str, UUID] = {}
        # Dedupe against priors loaded in two queries up front. The
        # old path ran a SELECT per (model, benchmark) — ~17 fields ×
        # hundreds of models — inside one transaction; on Neon from
        # the VPS that took ~20 min and the run died before commit,
        # so no AA data had landed since June.
        prior_results = await _latest_results(session)
        prior_speed = await _latest_signals(
            session, SignalSource.OUTPUT_TOKENS_PER_SECOND
        )
        results_written = 0
        signals_written = 0

        slug_to_agent = {
            a.slug.lower(): a.id
            for a in agents
            if a.entity_kind == "foundation_model"
        }
        by_agent = match_models(models, slug_to_agent)
        matched = len(by_agent)

        for aid, m in by_agent.items():
            # Benchmark fan-out.
            for aa_field, (bench_slug, category) in BENCHMARK_FIELD_MAP.items():
                score = _to_percent(aa_field, _dig(m, aa_field))
                if score is None:
                    continue
                if bench_slug not in bench_ids:
                    bench_ids[bench_slug] = await _ensure_benchmark(
                        session,
                        bench_slug,
                        AA_API,
                        category=category,
                        max_score=100.0,
                    )
                bid = bench_ids[bench_slug]
                if prior_results.get((aid, bid)) == score:
                    continue
                await _insert_result(session, aid, bid, captured, score)
                prior_results[(aid, bid)] = score
                results_written += 1

            # Efficiency: speed only. Price comes from
            # OpenRouterPricingIngestor, which covers every OpenRouter
            # model rather than just the AA-matched ones; writing it
            # here too would make the two sources overwrite each other.
            speed = _dig(m, "median_output_tokens_per_second")
            if speed is not None:
                try:
                    speed_f = round(float(speed), 6)
                except (ValueError, TypeError):
                    speed_f = 0.0
                if speed_f > 0 and prior_speed.get(aid) != speed_f:
                    await _insert_signal(
                        session,
                        aid,
                        SignalSource.OUTPUT_TOKENS_PER_SECOND,
                        speed_f,
                        captured,
                    )
                    prior_speed[aid] = speed_f
                    signals_written += 1

        await session.commit()
        log.info(
            "artificial_analysis: %d models fetched, %d matched, "
            "%d benchmark rows, %d signal rows",
            len(models),
            matched,
            results_written,
            signals_written,
        )
        return {
            "fetched": matched,
            "written": results_written + signals_written,
            "spiked": 0,
            "changed": 0,
            "matched": matched,
            "benchmark_rows": results_written,
            "signal_rows": signals_written,
        }


# ----------------------------------------------------------------- helpers


def _dig(obj: dict, path: str) -> Any:
    """Walk a dotted path into a nested dict. Returns None on miss."""
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


async def _ensure_benchmark(
    session: AsyncSession,
    slug: str,
    url: str,
    category: str,
    max_score: float,
) -> UUID:
    """Upsert the benchmarks row, return its id."""
    await session.execute(
        text(
            """
            INSERT INTO benchmarks (id, name, source_url, category, max_score, last_scraped_at)
            VALUES (gen_random_uuid(), :n, :u, :c, :m, NOW())
            ON CONFLICT (name) DO UPDATE SET
                source_url = EXCLUDED.source_url,
                category = EXCLUDED.category,
                max_score = EXCLUDED.max_score,
                last_scraped_at = NOW()
            """
        ),
        {"n": slug, "u": url, "c": category, "m": max_score},
    )
    r = await session.execute(
        text("SELECT id FROM benchmarks WHERE name = :n"), {"n": slug}
    )
    return r.scalar_one()


async def _latest_results(
    session: AsyncSession,
) -> dict[tuple[UUID, UUID], float]:
    """Latest score per (agent, benchmark), in one query."""
    r = await session.execute(
        text(
            """
            SELECT DISTINCT ON (agent_id, benchmark_id)
                agent_id, benchmark_id, score
            FROM benchmark_results
            ORDER BY agent_id, benchmark_id, captured_at DESC
            """
        )
    )
    return {(row[0], row[1]): float(row[2]) for row in r}


async def _latest_signals(
    session: AsyncSession, source: SignalSource
) -> dict[UUID, float]:
    """Latest value per agent for one signal source, in one query."""
    r = await session.execute(
        text(
            """
            SELECT DISTINCT ON (agent_id) agent_id, value
            FROM signals
            WHERE source = CAST(:src AS signal_source)
            ORDER BY agent_id, captured_at DESC
            """
        ),
        {"src": source.value},
    )
    return {row[0]: float(row[1]) for row in r}


async def _insert_result(
    session: AsyncSession,
    agent_id: UUID,
    benchmark_id: UUID,
    captured_at: datetime,
    score: float,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO benchmark_results (agent_id, benchmark_id, captured_at, score)
            VALUES (:aid, :bid, :ts, :s)
            ON CONFLICT (agent_id, benchmark_id, captured_at) DO UPDATE SET
                score = EXCLUDED.score
            """
        ),
        {"aid": agent_id, "bid": benchmark_id, "ts": captured_at, "s": score},
    )


async def _insert_signal(
    session: AsyncSession,
    agent_id: UUID,
    source: SignalSource,
    value: float,
    captured_at: datetime,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO signals (id, captured_at, agent_id, source, value)
            VALUES (gen_random_uuid(), :ts, :aid, CAST(:src AS signal_source), :val)
            """
        ),
        {"ts": captured_at, "aid": agent_id, "src": source.value, "val": value},
    )
