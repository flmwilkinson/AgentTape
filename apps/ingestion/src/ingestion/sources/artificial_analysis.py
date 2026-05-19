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

- **Cost** → ``OPENROUTER_PRICE_BLENDED`` signal (mean of
  input+output $/M). Naming reflects future plan to source from
  OpenRouter directly; AA is the current pragmatic source.

- **Speed** → ``OUTPUT_TOKENS_PER_SECOND`` signal.

Attribution required per AA's terms: methodology page links to
artificialanalysis.ai/methodology/intelligence-benchmarking.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


AA_API = "https://artificialanalysis.ai/api/v2/data/llms/models"


# AA response field → our ``benchmarks.name`` slug. When the slug
# already exists (e.g. gpqa-diamond, mmlu-pro), AA's value overwrites
# on the next tick — fine, AA's coverage is generally more
# comprehensive than what we scrape directly.
BENCHMARK_FIELD_MAP: dict[str, tuple[str, str]] = {
    # AA field name, (our benchmark slug, category)
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
    "evaluations.aime": ("aime-2025", "math"),
    "evaluations.livecodebench": ("livecodebench", "coding"),
    "evaluations.scicode": ("scicode", "reasoning"),
    "evaluations.humanitys_last_exam": ("hle", "reasoning"),
    "evaluations.terminal_bench_hard": ("terminal-bench-hard", "agentic"),
    "evaluations.tau2_bench_telecom": ("tau2-bench-telecom", "agentic"),
    "evaluations.ifbench": ("ifbench", "reasoning"),
    "evaluations.critpt": ("critpt", "coding"),
    "evaluations.aa_lcr": ("aa-lcr", "reasoning"),
    "evaluations.aa_omniscience": ("aa-omniscience", "reasoning"),
    "evaluations.gdpval_aa": ("gdpval-aa", "reasoning"),
}


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

        # Build slug → agent map. AA returns ``model_creator.slug`` +
        # ``slug``; we combine into ``{creator}-{model}`` which lines
        # up with our agent slugs. Exact key — no fuzzy matching, no
        # name-variant whack-a-mole.
        slug_to_agent: dict[str, UUID] = {a.slug.lower(): a.id for a in agents}

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
        results_written = 0
        signals_written = 0
        matched = 0

        for m in models:
            if not isinstance(m, dict):
                continue
            creator = (m.get("model_creator") or {}).get("slug")
            model_slug = m.get("slug")
            if not (creator and model_slug):
                continue
            key = f"{creator}-{model_slug}".lower()
            aid = slug_to_agent.get(key)
            if aid is None:
                # Also try AA's plain ``id`` field as a fallback —
                # some models on AA don't have the same slug shape.
                fallback = (m.get("id") or "").lower()
                aid = slug_to_agent.get(fallback)
            if aid is None:
                continue
            matched += 1

            # Benchmark fan-out.
            for aa_field, (bench_slug, category) in BENCHMARK_FIELD_MAP.items():
                value = _dig(m, aa_field)
                if value is None:
                    continue
                try:
                    score = float(value)
                except (ValueError, TypeError):
                    continue
                # AA inconsistently reports per-benchmark scores —
                # composite indices (intelligence_index, coding_index)
                # come on a 0-100 percentage scale, but individual
                # evaluations (gpqa, mmlu_pro, math_500, terminal_bench_hard)
                # often come as 0-1 fractions. Detect by magnitude:
                # anything <= 1.5 is a fraction, multiply by 100. Real
                # benchmark scores cluster 30-95 on the percentage scale,
                # so nothing legitimate lives in (1.5, 30) on either
                # scale — the threshold is safe.
                # Verified in prod: pre-fix, Claude Opus 4.7 had Quality
                # 31.5 instead of ~87 because GPQA / MMLU-Pro / SWE-bench
                # all wrote as 0.94 / 0.89 / 0.87 unchanged.
                if 0.0 <= score <= 1.5:
                    # Fraction → percentage. Cap at 100 because some
                    # AA fields exceed 1.0 (pass@K scoring on
                    # competition benchmarks like AIME, where 1.25
                    # = 125% relative-to-baseline). 1.25 * 100 = 125
                    # is meaningless on the 0-100 scale and inflates
                    # Quality averages. Verified in prod: GPT-5.1
                    # had AIME=125 and MMMU=125, pulling its
                    # Quality up to 81 when capped values would
                    # have given ~70.
                    score = min(score * 100.0, 100.0)
                elif not (0.0 <= score <= 100.0):
                    continue
                if bench_slug not in bench_ids:
                    bench_ids[bench_slug] = await _ensure_benchmark(
                        session,
                        bench_slug,
                        AA_API,
                        category=category,
                        max_score=100.0,
                    )
                if await _upsert_result(
                    session, aid, bench_ids[bench_slug], captured, score
                ):
                    results_written += 1

            # Efficiency signals — price (blended) + speed.
            in_price = _dig(m, "pricing.price_1m_input_tokens")
            out_price = _dig(m, "pricing.price_1m_output_tokens")
            if in_price is not None and out_price is not None:
                try:
                    blended = (float(in_price) + float(out_price)) / 2.0
                    if blended > 0:
                        if await _write_signal(
                            session,
                            aid,
                            SignalSource.OPENROUTER_PRICE_BLENDED,
                            blended,
                            captured,
                        ):
                            signals_written += 1
                except (ValueError, TypeError):
                    pass

            speed = _dig(m, "median_output_tokens_per_second")
            if speed is not None:
                try:
                    speed_f = float(speed)
                    if speed_f > 0:
                        if await _write_signal(
                            session,
                            aid,
                            SignalSource.OUTPUT_TOKENS_PER_SECOND,
                            speed_f,
                            captured,
                        ):
                            signals_written += 1
                except (ValueError, TypeError):
                    pass

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


async def _upsert_result(
    session: AsyncSession,
    agent_id: UUID,
    benchmark_id: UUID,
    captured_at: datetime,
    score: float,
) -> bool:
    """Insert-on-change. Returns True if a row was written."""
    r = await session.execute(
        text(
            """
            SELECT score FROM benchmark_results
            WHERE agent_id = :aid AND benchmark_id = :bid
            ORDER BY captured_at DESC LIMIT 1
            """
        ),
        {"aid": agent_id, "bid": benchmark_id},
    )
    row = r.first()
    if row is not None and float(row[0]) == score:
        return False

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
    return True


async def _write_signal(
    session: AsyncSession,
    agent_id: UUID,
    source: SignalSource,
    value: float,
    captured_at: datetime,
) -> bool:
    """Insert-on-change signal write. Returns True if written."""
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
    if row is not None and float(row[0]) == value:
        return False

    await session.execute(
        text(
            """
            INSERT INTO signals (id, captured_at, agent_id, source, value)
            VALUES (gen_random_uuid(), :ts, :aid, CAST(:src AS signal_source), :val)
            """
        ),
        {"ts": captured_at, "aid": agent_id, "src": source.value, "val": value},
    )
    return True
