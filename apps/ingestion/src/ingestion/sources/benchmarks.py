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
    # Aggregator homepage entries (galileo-agent-leaderboard,
    # hal-princeton, llm-stats-overview) were removed after Phase 2.
    # They were extracting noise numbers — rank cells, table-of-
    # contents counts, navigation chips — that don't represent any
    # particular benchmark and dragged Quality averages down for
    # well-covered models. Verified in prod: Claude Opus 4.7 had
    # llm-stats-overview=7.22 averaged into its Quality alongside
    # gpqa=91, ifbench=59, etc., pulling its Quality from ~85 down
    # to 60. The AA API covers the same benchmarks per-model now,
    # so the aggregator floor is no longer worth the noise.
    #
    # Per-benchmark llm-stats subpages — Phase 1 of the benchmarks
    # plan. Each is server-rendered enough that BeautifulSoup picks
    # up model name + score on the same row. If llm-stats reorganises
    # we lose these silently (per-site try/except in fetch). The
    # AA API ingestor provides redundant coverage for the same
    # benchmarks now, so a layout change on llm-stats degrades but
    # doesn't kill flagship Quality.
    #
    # Deliberate omissions: ``swe-bench-verified`` and ``mmlu-pro``
    # are already covered by FMLeaderboardsIngestor via canonical JSON
    # APIs (swe-bench.github.io master + TIGER-Lab HF dataset). The
    # canonical sources are higher fidelity than the llm-stats
    # aggregator, so we don't duplicate them here — fm_leaderboards
    # owns those two benchmark slugs. Add to ``LEADERBOARDS`` in
    # fm_leaderboards.py if you find a canonical JSON URL for any of
    # the benchmarks below — preferred over HTML scraping.
    BenchmarkSite(
        "gpqa-diamond",
        "GPQA Diamond",
        "https://llm-stats.com/benchmarks/gpqa",
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
        "mmmu",
        "MMMU",
        "https://llm-stats.com/benchmarks/mmmu",
        category="vision",
    ),
]


NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|points?)?\b")

# Score-shaped numbers in cell text, in priority order:
#   1. ``78.4%`` — number immediately followed by % (highest signal)
#   2. ``78.4`` — bare decimal in [1, 100], not adjacent to word chars
#      (skips version numbers like ``4.5`` inside ``Claude-Opus-4-5``
#      because hyphen counts as word-adjacent in our split — see
#      _extract_cell_score below for the row-cell walk)
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DECIMAL = re.compile(r"(?<![\w.\-])(\d+\.\d+)(?![\w.\-])")
_INTEGER = re.compile(r"(?<![\w.\-])(\d+)(?![\w.\-])")


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
    """Scan one page for rows mentioning this agent, return the
    most likely score from the rightmost score-shaped cell.

    Word-boundary matching is critical for FMs — naive substring
    containment makes ``gpt-5`` match every ``gpt-5-mini`` /
    ``gpt-5-pro`` row, so a model picks up its sibling's score. The
    shared ``word_boundary_regex`` helper enforces "matches the whole
    token, surrounded by non-alphanumerics" so ``gpt-5`` and
    ``gpt-5-mini`` no longer collide.

    Cell-based extraction (was: first-number-in-row-text):
        Previous behaviour grabbed the *first* number in the row's
        squashed text, which picked the model's version digits from
        the name cell — for "Claude Opus 4-5" it returned 4 or 5
        instead of the real score. Now we walk individual <td>/<th>
        cells and pick the rightmost cell whose text parses to a
        score-shaped value (percentage, then decimal in [1, 100],
        then integer). The name cell — where the version digits
        live — is just one of many cells and won't be selected as
        long as a numeric cell exists to its right.

        Bare ``<li>`` rows (no cells) fall back to a slightly
        smarter text extraction than before: prefer % matches over
        decimals over integers, still ignore numbers welded to word
        characters (so ``r1`` in ``deepseek-r1`` doesn't get
        confused for a score).
    """
    tokens = _identifying_tokens(a)
    if not tokens:
        return None
    pattern = word_boundary_regex(tokens)
    soup = BeautifulSoup(html, "html.parser")
    best: float | None = None
    # Only scan ``<tr>`` rows. ``<li>`` was previously included as a
    # safety net for sites that render leaderboards as flat lists, but
    # in practice every benchmark page we ingest uses a real table —
    # and ``<li>`` matches were polluting the data with model-card
    # sidebar elements like ``<li>Claude Opus 4.5</li>`` (the
    # navigation/related-models widget on llm-stats subpages). With
    # no cells inside that li, the extractor fell through to lenient
    # mode and grabbed "4.5" from the version digit in the model
    # name. Verified in prod: Opus 4.5 had 6 llm-stats rows all at
    # score=4.50 traced to this single ``<li>`` per page.
    for row in soup.find_all("tr"):
        full_text = row.get_text(" ", strip=True)
        if not pattern.search(full_text):
            continue
        score = _extract_row_score(row)
        if score is None:
            continue
        best = score if best is None else max(best, score)
    return best


def _extract_row_score(row) -> float | None:
    """Pull a score-shaped number out of a leaderboard ``<tr>`` row.

    Walks cells right-to-left and returns the first cell that parses
    to a score under ``strict=True`` — rejects name cells like
    ``"Claude Opus 4.5 Anthropic"`` whose ``4.5`` would otherwise
    leak through as a bogus score.

    Rows without ``<td>``/``<th>`` cells return None. The lenient
    fallback path used to exist for ``<li>`` rows but was removed
    after prod data showed it leaked version digits from model-card
    navigation elements (``<li>Claude Opus 4.5</li>``).
    """
    cells = row.find_all(["td", "th"])
    if not cells:
        return None
    # Rightmost cells first — leaderboards conventionally put the
    # headline score in the last data column. ``strict`` rejects
    # cells with more than a couple of letters so the walk skips
    # name cells like "Claude Opus 4.5 Anthropic" and continues
    # looking for a numeric-dominant cell.
    for cell in reversed(cells):
        text_ = cell.get_text(" ", strip=True)
        v = _extract_cell_score(text_, strict=True)
        if v is not None:
            return v
    return None


def _extract_cell_score(text_: str, strict: bool = False) -> float | None:
    """Pick the most likely score-shaped number from a cell's text.

    Priority order (each step takes the LARGEST value in range — score
    numbers reliably beat version digits / parameter counts because
    benchmark scores cluster high while version digits cluster low):

      1. ``78.4%`` — percentage suffix is the highest-confidence signal
      2. ``78.4`` or ``0.934`` — bare decimal in [0, 100], not adjacent
         to word chars. Decimals <= 1.5 are treated as 0-1 fractions
         and multiplied by 100 (llm-stats uses ``0.934 = 93.4%``
         throughout). Decimals > 1.5 are treated as percentages.
      3. ``78`` — bare integer in [1, 100] not adjacent to word chars

    ``strict`` mode (default False): when True, reject cells whose
    text contains more than 2 alphabetic characters. This blocks the
    name-cell leak where the right-to-left walk falls through empty
    score cells into the model-name cell and extracts version digits
    as a score. Verified in prod: pre-fix slow-tier wrote ``score=4.50``
    for Claude Opus 4.5 on every llm-stats benchmark because cell [2]
    (the score column) was empty/— and the walk fell through to
    cell [1] = "Claude Opus 4.5 Anthropic" → matched "4.5".

    Three prior bugs all fixed in this extractor:

    * Returning the LARGEST (not first) — rows like
      "OpenAI GPT-5 5.1B 92%" returned 5.1 (parameter count) before
      reaching 92 (score).
    * Accepting [0, 100] not [1, 100] + fraction-aware — rows like
      "4 GPT-5 OpenAI 0.934" returned 4 (rank) because 0.934 was
      below the lower bound. llm-stats publishes ALL scores as
      [0, 1] fractions.
    * ``strict`` name-cell rejection — empty score cells caused
      right-to-left walk to fall through to name cells and extract
      version digits ("4.5" from "Claude Opus 4.5").

    None when nothing matches — we under-emit rather than fabricate.
    """
    if strict:
        # Score cells are numeric-dominant. Model-name cells like
        # "Claude Opus 4.5 Anthropic" or "GPT-5 OpenAI" have many
        # letters and their digits are version numbers, not scores.
        # >2 letters is the threshold — allows short tags like "Acc"
        # or unit hints in numeric cells, blocks any real name.
        letters = sum(1 for c in text_ if c.isalpha())
        if letters > 2:
            return None

    # 1. Percentage with explicit %
    pct_values = [
        float(m.group(1))
        for m in _PCT.finditer(text_)
        if _safe_in_range(m.group(1), 0.0, 100.0)
    ]
    if pct_values:
        return max(pct_values)

    # 2. Bare decimals in [0, 100], fractions auto-scaled.
    #    Magnitude-based disambiguation (<=1.5 = fraction, >1.5 =
    #    percentage) works because real benchmark scores cluster at
    #    30-95% on the percentage scale; nothing legitimately lives
    #    in (1.5, 30) on either scale, so the threshold is safe.
    decimals: list[float] = []
    for m in _DECIMAL.finditer(text_):
        try:
            v = float(m.group(1))
        except ValueError:
            continue
        if not (0.0 <= v <= 100.0):
            continue
        decimals.append(v * 100.0 if v <= 1.5 else v)
    if decimals:
        return max(decimals)

    # 3. Bare integers in [1, 100]. Integers don't get the fraction
    #    treatment — a bare "1" is almost certainly a rank or a count,
    #    not a 100% score. Real perfect scores would render as 1.0
    #    (decimal) on a fractional scale.
    integers = [
        float(m.group(1))
        for m in _INTEGER.finditer(text_)
        if _safe_in_range(m.group(1), 1.0, 100.0)
    ]
    if integers:
        return max(integers)

    return None


def _safe_in_range(s: str, lo: float, hi: float) -> bool:
    try:
        v = float(s)
    except ValueError:
        return False
    return lo <= v <= hi


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
