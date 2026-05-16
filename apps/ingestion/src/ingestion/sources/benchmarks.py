"""Benchmark leaderboards.

Each entry in ``SITES`` is treated as one benchmark in its own right.
Per slow-tier tick, we fetch each page, scan it for agent-identifying
tokens, pluck the first number on the matching row, and emit two
things per agent:

1. A row in ``benchmark_results`` keyed by
   ``(agent_id, benchmark_id, captured_at)``. This is what the scoring
   pillar formula reads from — ``_agent_benchmark_score`` normalises
   each per-benchmark score against the benchmark's ``max_score`` and
   averages them, so the Quality pillar gets a per-sector-aware
   number rather than a flat max.
2. A ``BENCHMARK_SCORE`` signal whose value is the mean of this tick's
   normalised per-benchmark scores for that agent. Keeps the
   change/spike machinery on the ``signals`` table working
   (dedupe, redis publish, spike events), and means historical
   queries against ``signals`` keep producing a sensible "overall
   benchmark health" number per agent.

Per-site try/except is preserved — one bad layout can't brick the run.

History
-------
The previous ingestor took the **max** across every benchmark page and
wrote a single per-tick ``BENCHMARK_SCORE`` signal. That collapsed
sector resolution: a coding agent's irrelevant GAIA score could
mask its LiveCodeBench score. The ``benchmark_results`` table was
already in the schema but nothing wrote to it, so the scoring code's
``_agent_benchmark_score`` was reading from an empty table and
silently returning None for every agent's Quality pillar
contribution from benchmarks.

The first three entries (galileo, hal, llm-stats homepage) are kept
as ``category="aggregator"``. They scrape multiple benchmarks on one
page so the score there is "best score this agent had visible on
that aggregator" — a useful floor signal, not authoritative per
benchmark.

The remaining entries are per-benchmark llm-stats subpages. Each is
its own row in ``benchmarks`` with ``max_score=100`` (llm-stats
publishes percentages). Adding new per-benchmark URLs from llm-stats
is a one-line change here — the schema and the scoring code already
handle it.

AstaBench (allenai.github.io/asta-bench/) and Steel WebVoyager
(steel.dev/webvoyager) were here previously but both URLs 404 as
of 2026-05. Dropped from the seed list rather than chase moved
pages — when we find replacements with stable URLs we'll re-add
them. Adding a dead URL just prints a warning and skips, so
there's no functional damage either way, but the log noise was
obscuring the real failures.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID

from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.name_tokens import search_tokens, word_boundary_regex

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkSite:
    """One scrapable benchmark leaderboard.

    ``slug`` doubles as the row's ``benchmarks.name`` — uniqueness on
    that column is what makes the upsert path idempotent across runs.
    ``max_score`` is the value a perfect score on this benchmark
    would take in the page text; 100 for the standard percentage
    leaderboards. Used to normalise scores before averaging across
    benchmarks in the scoring pillar.
    """

    slug: str
    display_name: str
    url: str
    category: str
    max_score: float = 100.0


SITES: list[BenchmarkSite] = [
    # Aggregators — multi-benchmark pages. Score here is "best number
    # visible on this aggregator", treated as a floor signal rather
    # than a canonical per-benchmark result.
    BenchmarkSite(
        "galileo-agent-leaderboard",
        "Galileo Agent Leaderboard",
        "https://huggingface.co/spaces/galileo-ai/agent-leaderboard",
        category="aggregator",
    ),
    BenchmarkSite(
        "hal-princeton",
        "HAL (Princeton)",
        "https://hal.cs.princeton.edu/",
        category="aggregator",
    ),
    BenchmarkSite(
        "llm-stats-overview",
        "LLM-Stats overview",
        "https://llm-stats.com/",
        category="aggregator",
    ),
    # Per-benchmark llm-stats subpages — Phase 1 of the benchmarks
    # plan. Each is server-rendered enough that BeautifulSoup picks
    # up model name + score on the same row. If llm-stats reorganises
    # we lose these silently (per-site try/except in fetch) and the
    # aggregator rows above stay as a fallback floor.
    BenchmarkSite(
        "gpqa-diamond",
        "GPQA Diamond",
        "https://llm-stats.com/benchmarks/gpqa",
        category="reasoning",
    ),
    BenchmarkSite(
        "mmlu-pro",
        "MMLU-Pro",
        "https://llm-stats.com/benchmarks/mmlu-pro",
        category="reasoning",
    ),
    BenchmarkSite(
        "aime-2025",
        "AIME 2025",
        "https://llm-stats.com/benchmarks/aime-2025",
        category="math",
    ),
    BenchmarkSite(
        "math",
        "MATH",
        "https://llm-stats.com/benchmarks/math",
        category="math",
    ),
    BenchmarkSite(
        "humaneval",
        "HumanEval",
        "https://llm-stats.com/benchmarks/humaneval",
        category="coding",
    ),
    BenchmarkSite(
        "livecodebench",
        "LiveCodeBench",
        "https://llm-stats.com/benchmarks/livecodebench",
        category="coding",
    ),
    BenchmarkSite(
        "swe-bench-verified",
        "SWE-Bench Verified",
        "https://llm-stats.com/benchmarks/swe-bench-verified",
        category="coding",
    ),
    BenchmarkSite(
        "mmmu",
        "MMMU",
        "https://llm-stats.com/benchmarks/mmmu",
        category="vision",
    ),
]


NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|points?)?\b")


@dataclass(frozen=True)
class _PerBenchmarkHit:
    agent_id: UUID
    site: BenchmarkSite
    score: float
    captured_at: datetime


class BenchmarksIngestor(Ingestor):
    name: ClassVar[str] = "benchmarks"
    source: ClassVar[SignalSource] = SignalSource.BENCHMARK_SCORE
    tier: ClassVar[str] = "slow"

    # Populated by ``fetch`` each tick, consumed by ``run`` to write
    # the per-benchmark rows. Kept as instance state rather than a
    # return-value extension so the base ``Ingestor`` contract stays
    # unchanged (one method, one shape).
    _per_benchmark: list[_PerBenchmarkHit]

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # One HTML fetch per site, cached implicitly by today's tick.
        pages: dict[str, tuple[BenchmarkSite, str]] = {}
        for site in SITES:
            html = await _fetch_html(self._http, site.url)
            if html is not None:
                pages[site.slug] = (site, html)

        captured = datetime.now(UTC)
        self._per_benchmark = []
        out: list[SignalReading] = []
        for a in agents:
            per_agent: list[tuple[BenchmarkSite, float]] = []
            for site, html in pages.values():
                score = _score_for_agent_on_page(a, html)
                if score is None:
                    continue
                self._per_benchmark.append(
                    _PerBenchmarkHit(a.id, site, score, captured)
                )
                per_agent.append((site, score))
            if not per_agent:
                continue
            # Normalise against each benchmark's max_score before
            # averaging — matches what ``_agent_benchmark_score`` does
            # at pillar-compute time, so the per-tick signal and the
            # cross-tick query stay numerically consistent.
            normalised = [
                min(100.0, max(0.0, s / site.max_score * 100.0))
                for site, s in per_agent
            ]
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.BENCHMARK_SCORE,
                    value=sum(normalised) / len(normalised),
                    captured_at=captured,
                )
            )
        return out

    async def run(
        self, session: AsyncSession, agents: list[AgentRow], redis_client
    ) -> dict[str, int]:
        # Standard path first — writes BENCHMARK_SCORE signals,
        # dedupes, spike-detects, publishes. ``fetch`` (called from
        # inside super().run) populates ``self._per_benchmark`` as a
        # side effect.
        result = await super().run(session, agents, redis_client)

        per = getattr(self, "_per_benchmark", [])
        if not per:
            return result

        # Upsert ``benchmarks`` rows for each site we got a hit on
        # this tick. Lazy upsert avoids a seed migration every time a
        # new BenchmarkSite is added.
        benchmark_ids: dict[str, UUID] = {}
        for site in {hit.site for hit in per}:
            benchmark_ids[site.slug] = await _upsert_benchmark(session, site)

        written = 0
        deduped = 0
        for hit in per:
            bid = benchmark_ids[hit.site.slug]
            prior = await _last_benchmark_score(session, hit.agent_id, bid)
            if prior is not None and prior == hit.score:
                deduped += 1
                continue
            # Composite PK is (agent_id, benchmark_id, captured_at).
            # ON CONFLICT covers the rare case of two ingestion runs
            # firing in the same second (e.g. retry after partial
            # failure) — we just overwrite with the latest scrape.
            await session.execute(
                text(
                    """
                    INSERT INTO benchmark_results
                        (agent_id, benchmark_id, captured_at, score)
                    VALUES (:aid, :bid, :ts, :s)
                    ON CONFLICT (agent_id, benchmark_id, captured_at)
                        DO UPDATE SET score = EXCLUDED.score
                    """
                ),
                {
                    "aid": hit.agent_id,
                    "bid": bid,
                    "ts": hit.captured_at,
                    "s": hit.score,
                },
            )
            written += 1
        await session.commit()
        log.info(
            "benchmarks per-result: %d hits, %d written, %d deduped",
            len(per),
            written,
            deduped,
        )
        result["benchmark_results_written"] = written
        result["benchmark_results_deduped"] = deduped
        return result


async def _fetch_html(http, url: str) -> str | None:
    try:
        r = await http.get(url)
    except Exception as e:  # noqa: BLE001
        log.warning("benchmark fetch %s: %s", url, e)
        return None
    if r.status_code != 200:
        log.warning("benchmark %s returned %d", url, r.status_code)
        return None
    return r.text


def _score_for_agent_on_page(a: AgentRow, html: str) -> float | None:
    """Best-effort: scan one page for the agent's identifying tokens
    and pluck the first number on the same row.

    Word-boundary matching is critical for FMs — naive substring
    containment makes ``gpt-5`` match every ``gpt-5-mini`` /
    ``gpt-5-pro`` row on a leaderboard, so a model picks up its
    sibling's score. The shared ``word_boundary_regex`` helper
    enforces "matches the whole token, surrounded by non-alphanumerics"
    so ``gpt-5`` and ``gpt-5-mini`` no longer collide.
    """
    tokens = _identifying_tokens(a)
    if not tokens:
        return None
    pattern = word_boundary_regex(tokens)
    soup = BeautifulSoup(html, "html.parser")
    best: float | None = None
    for tr in soup.find_all(["tr", "li"]):
        text_ = tr.get_text(" ", strip=True)
        if not pattern.search(text_):
            continue
        m = NUMBER.search(text_)
        if not m:
            continue
        try:
            value = float(m.group(1))
        except ValueError:
            continue
        best = value if best is None else max(best, value)
    return best


def _identifying_tokens(a: AgentRow) -> list[str]:
    """Build a token list per agent. For FMs, defer to
    ``search_tokens`` which knows how to derive clean display names
    ("GPT-5") from the slug + facts. For applications, use the slug,
    repo last segment, and HF model ids — the existing logic.
    """
    if a.entity_kind == "foundation_model":
        return search_tokens(a)
    tokens = [a.slug]
    if a.github_repo:
        last = a.github_repo.split("/")[-1]
        if len(last) >= 4:
            tokens.append(last)
    for hf_id in a.hf_model_ids or []:
        tokens.append(hf_id)
    return tokens


async def _upsert_benchmark(
    session: AsyncSession, site: BenchmarkSite
) -> UUID:
    """Return the ``benchmarks.id`` for this site, inserting if absent.

    Uniqueness is on ``benchmarks.name``, which we keep as the site's
    machine slug. The UPDATE branch refreshes ``source_url``,
    ``category``, ``max_score`` and ``last_scraped_at`` so editing
    ``SITES`` in code is enough to fix wrong metadata — no manual SQL.
    """
    r = await session.execute(
        text(
            """
            INSERT INTO benchmarks
                (id, name, source_url, category, max_score, last_scraped_at)
            VALUES
                (gen_random_uuid(), :n, :u, :c, :m, NOW())
            ON CONFLICT (name) DO UPDATE
              SET source_url = EXCLUDED.source_url,
                  category = EXCLUDED.category,
                  max_score = EXCLUDED.max_score,
                  last_scraped_at = NOW()
            RETURNING id
            """
        ),
        {
            "n": site.slug,
            "u": site.url,
            "c": site.category,
            "m": site.max_score,
        },
    )
    return r.scalar_one()


async def _last_benchmark_score(
    session: AsyncSession, agent_id: UUID, benchmark_id: UUID
) -> float | None:
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
    return float(row[0]) if row else None
