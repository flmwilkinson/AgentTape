"""Benchmark leaderboards.

Each benchmark site is fetched once per slow tier tick, parsed, and
matched against admitted agents (by slug, github_repo last segment, or
hf id). Per-site try/except: a layout change on one leaderboard must
not brick the whole daily run.

Sites:
    - Galileo Agent Leaderboard
    - HAL (Hallucinations leaderboard)
    - LLM-Stats

The HTML layouts here change without notice. We attempt structured
extraction first (any JSON-LD or data-* attributes), then fall back to
matching agent identifiers against the page text. Misses are logged
silently — we'd rather under-emit than emit garbage.

History:
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

from bs4 import BeautifulSoup

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkSite:
    name: str
    url: str


SITES: list[BenchmarkSite] = [
    BenchmarkSite(
        "galileo-agent-leaderboard",
        "https://huggingface.co/spaces/galileo-ai/agent-leaderboard",
    ),
    BenchmarkSite("hal", "https://hal.cs.princeton.edu/"),
    BenchmarkSite("llm-stats", "https://llm-stats.com/"),
]

NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|points?)?\b")


class BenchmarksIngestor(Ingestor):
    name: ClassVar[str] = "benchmarks"
    source: ClassVar[SignalSource] = SignalSource.BENCHMARK_SCORE
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # One HTML fetch per site, cached implicitly by today's tick.
        pages: dict[str, str] = {}
        for site in SITES:
            html = await _fetch_html(self._http, site.url)
            if html is not None:
                pages[site.name] = html

        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            best = _best_score_for_agent(a, pages)
            if best is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.BENCHMARK_SCORE,
                    value=float(best),
                    captured_at=captured,
                )
            )
        return out


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


def _best_score_for_agent(a: AgentRow, pages: dict[str, str]) -> float | None:
    """Best-effort: scan each page for the agent's identifying tokens
    and pluck the first number on the same row.

    This is intentionally simple. A site-specific parser would be more
    accurate; the goal here is for the slow tier to *do something*
    plausible across five layouts we don't control.
    """
    tokens = _identifying_tokens(a)
    best: float | None = None
    for html in pages.values():
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.find_all(["tr", "li"]):
            text = tr.get_text(" ", strip=True)
            tl = text.lower()
            if not any(tok in tl for tok in tokens):
                continue
            m = NUMBER.search(text)
            if not m:
                continue
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            best = value if best is None else max(best, value)
    return best


def _identifying_tokens(a: AgentRow) -> list[str]:
    tokens = [a.slug.lower()]
    if a.github_repo:
        last = a.github_repo.split("/")[-1].lower()
        if len(last) >= 4:  # skip noisy two-letter org repos
            tokens.append(last)
    for hf_id in a.hf_model_ids or []:
        tokens.append(hf_id.lower())
    return tokens
