"""Per-source parsing tests with httpx.MockTransport.

These verify that each source's ``fetch`` produces well-shaped
``SignalReading`` objects from canned upstream responses. No network.
"""
from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from ingestion.config import Settings
from ingestion.enums import SignalSource
from ingestion.sources.arxiv import ArxivIngestor
from ingestion.sources.base import AgentRow
from ingestion.sources.benchmarks import BenchmarksIngestor
from ingestion.sources.github import GithubStarsIngestor
from ingestion.sources.hackernews import HNMentions7dIngestor
from ingestion.sources.huggingface import (
    HFDownloads30dIngestor,
    HFTrendingRankIngestor,
)
from ingestion.sources.mcp import MCPRegistryListedIngestor
from ingestion.sources.packages import NPMWeeklyIngestor
from ingestion.sources.semantic_scholar import ArxivCitationsIngestor

pytestmark = pytest.mark.asyncio


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )


def _agent(**overrides: Any) -> AgentRow:
    base = dict(
        id=uuid.uuid4(),
        slug="example-agent",
        name="Example Agent",
        github_repo="example/agent",
        hf_org=None,
        hf_model_ids=None,
        package_names=None,
        arxiv_ids=None,
        facts=None,
        entity_kind="application",
    )
    base.update(overrides)
    return AgentRow(**base)


# ---------------------------------------------------------------- github


async def test_github_stars_uses_rest_without_token():
    settings = Settings(github_token=None)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/example/agent"):
            return httpx.Response(200, json={"stargazers_count": 1234, "forks_count": 56})
        return httpx.Response(404)

    ing = GithubStarsIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([_agent()])
    finally:
        await ing.aclose()

    assert len(readings) == 1
    r = readings[0]
    assert r.source == SignalSource.GITHUB_STARS
    assert r.value == 1234.0


async def test_github_stars_uses_graphql_with_token():
    settings = Settings(github_token="x")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com" and request.url.path == "/graphql":
            import json
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "data": {
                        "r0": {"stargazerCount": 42},
                    }
                },
            )
        return httpx.Response(404)

    ing = GithubStarsIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([_agent()])
    finally:
        await ing.aclose()

    assert "query" in captured["body"]
    assert "stargazerCount" in captured["body"]["query"]
    assert readings[0].value == 42.0


async def test_github_stars_skips_agents_without_repo():
    settings = Settings()
    a = _agent(github_repo=None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)  # Should never be hit.

    ing = GithubStarsIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings == []


# -------------------------------------------------------------- huggingface


async def test_hf_trending_rank_finds_agent_in_list():
    settings = Settings()
    a = _agent(hf_model_ids=["acme/agent-large"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/models":
            return httpx.Response(
                200,
                json=[
                    {"id": "anthropic/claude-agent"},
                    {"id": "acme/agent-large"},
                    {"id": "other/model"},
                ],
            )
        return httpx.Response(404)

    ing = HFTrendingRankIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert len(readings) == 1
    assert readings[0].source == SignalSource.HF_TRENDING_RANK
    assert readings[0].value == 2.0  # 1-indexed


async def test_hf_downloads_per_model():
    settings = Settings()
    a = _agent(hf_model_ids=["acme/agent-large"])

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/models/acme/agent-large" in request.url.path:
            return httpx.Response(200, json={"downloads": 50000, "likes": 100})
        return httpx.Response(404)

    ing = HFDownloads30dIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 50000.0


# ---------------------------------------------------------------- packages


async def test_npm_weekly_reads_downloads():
    settings = Settings()
    a = _agent(package_names={"npm": "agentic-toolkit"})

    def handler(request: httpx.Request) -> httpx.Response:
        if "agentic-toolkit" in request.url.path:
            return httpx.Response(200, json={"downloads": 9999, "package": "agentic-toolkit"})
        return httpx.Response(404)

    ing = NPMWeeklyIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 9999.0


# ---------------------------------------------------------------- hn


async def test_hn_mentions_returns_count():
    settings = Settings()
    a = _agent()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hn.algolia.com":
            return httpx.Response(200, json={"nbHits": 7})
        return httpx.Response(404)

    ing = HNMentions7dIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 7.0


# ---------------------------------------------------------------- mcp


async def test_mcp_registry_listed_emits_one_per_agent():
    settings = Settings()
    a_listed = _agent(slug="filesystem", github_repo="modelcontextprotocol/servers")
    a_missing = _agent(slug="random", github_repo="example/random")

    def handler(request: httpx.Request) -> httpx.Response:
        if "registry.modelcontextprotocol.io" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "servers": [
                        {
                            "name": "filesystem",
                            "repository": {"url": "https://github.com/modelcontextprotocol/servers"},
                        }
                    ],
                    "metadata": {"next_cursor": None},
                },
            )
        if "glama.ai" in request.url.host:
            return httpx.Response(200, json={"servers": []})
        return httpx.Response(404)

    ing = MCPRegistryListedIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a_listed, a_missing])
    finally:
        await ing.aclose()
    by_agent = {r.agent_id: r.value for r in readings}
    assert by_agent[a_listed.id] == 1.0
    assert by_agent[a_missing.id] == 0.0


# ---------------------------------------------------------------- arxiv


async def test_arxiv_mentions_counts_entries():
    settings = Settings()
    a = _agent()

    atom = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
        <entry><id>1</id></entry>
        <entry><id>2</id></entry>
        <entry><id>3</id></entry>
    </feed>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=atom)

    ing = ArxivIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 3.0


# ---------------------------------------------------------------- benchmarks


async def test_benchmarks_emits_per_benchmark_and_mean():
    """fetch() must populate both outputs from one pass:

    - ``_per_benchmark`` (side store, consumed by run() to write
      benchmark_results rows) — one hit per (agent, site) match
    - return value: one SignalReading per agent whose value is the
      mean of normalised per-benchmark scores. The mean preserves
      the existing dedupe + spike machinery on the signals table
      and matches what _agent_benchmark_score does at pillar time,
      so the two views stay numerically consistent.
    """
    settings = Settings()
    a = _agent(slug="acme-agent", entity_kind="application")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # Match the agent on two per-benchmark llm-stats pages with
        # different scores. Other pages return 404 (silently skipped).
        if "/benchmarks/gpqa" in url:
            return httpx.Response(
                200,
                text="<table><tr><td>acme-agent</td><td>80.0%</td></tr></table>",
            )
        if "/benchmarks/humaneval" in url:
            return httpx.Response(
                200,
                text="<table><tr><td>acme-agent</td><td>60.0%</td></tr></table>",
            )
        return httpx.Response(404)

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    assert len(readings) == 1
    r = readings[0]
    assert r.source == SignalSource.BENCHMARK_SCORE
    # Mean of normalised (max_score=100 → percentages used as-is): 70.0
    assert r.value == pytest.approx(70.0)

    by_slug = {hit.site.slug: hit.score for hit in ing._per_benchmark}
    assert by_slug == {"gpqa-diamond": 80.0, "humaneval": 60.0}


async def test_benchmarks_ignores_version_digits_in_model_name():
    """Regression test for the prod bug where the legacy first-number
    extractor returned ``5`` from ``GPT-5`` cells and ``4.5`` from
    ``Claude Opus 4-5`` cells — making every llm-stats subpage scrape
    return version digits instead of real scores.

    The fix is cell-based: walk <td> cells right-to-left, pick the
    rightmost cell that parses to a score-shaped value. The name
    cell (which contains the version) is rejected because its text
    has no standalone score-shaped number — the version digits are
    welded to word characters via hyphens.
    """
    # Real-shape FM agent — search_tokens() will derive "gpt-5" etc.
    a = _agent(
        slug="openai-gpt-5",
        entity_kind="foundation_model",
        github_repo=None,
        facts={
            "openrouter_id": "openai/gpt-5",
            "display_name": "GPT-5",
        },
    )

    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # llm-stats-shaped row: model in first cell, $price cells, score last.
        # Pre-fix: regex grabbed "5" from "gpt-5". Post-fix: walks cells,
        # rightmost is "78.4%" → returns 78.4.
        if "/benchmarks/gpqa" in url:
            return httpx.Response(
                200,
                text=(
                    "<table><tr>"
                    "<td>OpenAI: GPT-5</td>"
                    "<td>$2.00</td><td>$10.00</td>"
                    "<td>78.4%</td>"
                    "</tr></table>"
                ),
            )
        return httpx.Response(404)

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    assert len(readings) == 1
    assert readings[0].value == pytest.approx(78.4)
    by_slug = {hit.site.slug: hit.score for hit in ing._per_benchmark}
    assert by_slug == {"gpqa-diamond": 78.4}


async def test_benchmarks_picks_largest_score_over_parameter_count():
    """Regression for the prod follow-on bug: llm-stats rows render
    model size before the score, like ``"OpenAI GPT-5 5.1B 92%"``.
    A first-match extractor returned ``5.1`` (parameter count). The
    fix prefers the LARGEST decimal in [1, 100] within each priority
    tier — score numbers reliably beat parameter counts because
    benchmarks cluster in 30-95 while sizes cluster in 0.5-9.5.
    """
    a = _agent(
        slug="openai-gpt-5",
        entity_kind="foundation_model",
        github_repo=None,
        facts={"openrouter_id": "openai/gpt-5", "display_name": "GPT-5"},
    )
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/benchmarks/humaneval" in url:
            # Real-shape llm-stats cell: model name + parameter count
            # + score, all in one <td> (Next.js often collapses cells
            # into a single styled div per row).
            return httpx.Response(
                200,
                text=(
                    "<table><tr>"
                    "<td>OpenAI GPT-5 5.1B 92.3%</td>"
                    "</tr></table>"
                ),
            )
        return httpx.Response(404)

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    assert len(readings) == 1
    # Pre-fix: returned 5.1 (parameter count). Post-fix: returns 92.3.
    assert readings[0].value == pytest.approx(92.3)


async def test_benchmarks_handles_llmstats_fractional_scores():
    """Regression for the second prod follow-on bug: llm-stats publishes
    scores as 0-1 fractions, not 0-100 percentages. The prod row for
    GPT-5 on HumanEval looked exactly like this:

        cells = ["4", "GPT-5 OpenAI", "0.934", "—", "—", "—", ""]

    Pre-fix extractor rejected 0.934 (below the [1, 100] floor) and
    fell through to the rank cell "4", returning 4.0. Fix accepts
    decimals in [0, 100] and auto-scales fractions (anything <= 1.5)
    by 100.
    """
    a = _agent(
        slug="openai-gpt-5",
        entity_kind="foundation_model",
        github_repo=None,
        facts={"openrouter_id": "openai/gpt-5", "display_name": "GPT-5"},
    )
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if "/benchmarks/humaneval" in str(request.url):
            return httpx.Response(
                200,
                text=(
                    "<table><tr>"
                    "<td>4</td>"
                    "<td>GPT-5 OpenAI</td>"
                    "<td>0.934</td>"
                    "<td>—</td><td>—</td><td>—</td><td></td>"
                    "</tr></table>"
                ),
            )
        return httpx.Response(404)

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    assert len(readings) == 1
    # Pre-fix: returned 4.0 (the rank). Post-fix: 0.934 * 100 = 93.4.
    assert readings[0].value == pytest.approx(93.4)


async def test_benchmarks_skips_agent_with_no_hits():
    """An agent that doesn't appear on any leaderboard page emits
    no signal reading and no per-benchmark hits — the ingestor must
    under-emit rather than fabricate."""
    settings = Settings()
    # No github_repo on purpose — the default fixture's "example/agent"
    # tail-segment ("agent") would token-match "other-agent" below and
    # mask the empty-result case we're testing for.
    a = _agent(
        slug="nobody-knows-me",
        github_repo=None,
        entity_kind="application",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        # Page returns 200 but doesn't contain our agent's tokens.
        return httpx.Response(
            200, text="<table><tr><td>other-agent</td><td>99.0%</td></tr></table>"
        )

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    assert readings == []
    assert ing._per_benchmark == []


async def test_semantic_scholar_sums_citations():
    settings = Settings()
    a = _agent(arxiv_ids=["2604.01234", "2605.99999"])

    def handler(request: httpx.Request) -> httpx.Response:
        if "2604.01234" in request.url.path:
            return httpx.Response(200, json={"citationCount": 10})
        if "2605.99999" in request.url.path:
            return httpx.Response(200, json={"citationCount": 7})
        return httpx.Response(404)

    ing = ArxivCitationsIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 17.0
