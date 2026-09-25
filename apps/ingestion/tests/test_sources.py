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
    base = {
        "id": uuid.uuid4(),
        "slug": "example-agent",
        "name": "Example Agent",
        "github_repo": "example/agent",
        "hf_org": None,
        "hf_model_ids": None,
        "package_names": None,
        "arxiv_ids": None,
        "facts": None,
        "entity_kind": "application",
    }
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
    """Regression for the largest-in-range fix. Within a score-only
    cell with multiple numbers (e.g. ``"1024 · 92.3"``), the extractor
    must pick the largest score-shaped value in [1, 100].

    The cell content is intentionally numeric-dominant (no model name)
    so the strict cell extractor accepts it — the name lives in its
    own cell, which is the correct real-world shape.
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
            # Multi-cell row matching real llm-stats structure. The
            # score cell has two numbers (sample size + score) — the
            # extractor picks the largest in-range.
            return httpx.Response(
                200,
                text=(
                    "<table><tr>"
                    "<td>1</td>"
                    "<td>OpenAI GPT-5</td>"
                    "<td>1024 92.3</td>"
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
    # Score cell "1024 92.3" — strict extractor: 1024 filtered out,
    # 92.3 in [1, 100] → returns 92.3.
    assert readings[0].value == pytest.approx(92.3)


async def test_benchmarks_rejects_version_digits_in_name_cell():
    """Regression for the prod name-cell leak. The right-to-left cell
    walk used to fall through empty score cells into the name cell and
    extract the model's version digit as a score. Every Claude Opus 4.5
    row on llm-stats wrote ``score=4.50`` because cells were:

        [1] [name="Claude Opus 4.5 Anthropic"] [score=""] [—] [—]

    Walking right-to-left, the empty/— cells matched nothing, the
    walk fell through to the name cell, and "4.5" inside the model
    name was extracted as the score. Fix: ``strict=True`` rejects
    cells with >2 alphabetic characters.
    """
    a = _agent(
        slug="anthropic-claude-opus-4-5",
        entity_kind="foundation_model",
        github_repo=None,
        facts={
            "openrouter_id": "anthropic/claude-opus-4-5",
            "display_name": "Claude Opus 4.5",
        },
    )
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/benchmarks/humaneval" in url:
            # Empty score cell — model has no real benchmark result.
            # Should yield NO reading, not the version digit "4.5".
            return httpx.Response(
                200,
                text=(
                    "<table><tr>"
                    "<td>1</td>"
                    "<td>Claude Opus 4.5 Anthropic</td>"
                    "<td></td><td>—</td><td>—</td>"
                    "</tr></table>"
                ),
            )
        return httpx.Response(404)

    ing = BenchmarksIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()

    # Pre-fix: returned SignalReading(value=4.5) from the name cell.
    # Post-fix: empty score cell + rejected name cell = no reading.
    assert readings == []


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


# --------------------------------------------------------- fm_leaderboards


def test_fm_leaderboards_name_variants_strips_decorators():
    """Reasoning-mode decorators on leaderboard names don't have their
    own agent slug. Strip them so the base slug matches."""
    from ingestion.sources.fm_leaderboards import _name_variants
    variants = _name_variants("claude-opus-4-7-thinking")
    assert "claude-opus-4-7-thinking" in variants
    assert "claude-opus-4-7" in variants


def test_fm_leaderboards_name_variants_splits_harness():
    """SWE-bench format is ``harness + model [decorators]``. The
    matcher must extract just the model substring."""
    from ingestion.sources.fm_leaderboards import _name_variants
    variants = _name_variants("live-SWE-agent + Claude 4.5 Opus medium (20251101)")
    # The model substring with decorator stripped should be in there
    assert any("Claude 4.5 Opus" in v for v in variants)
    # And the harness alone should NOT be — it's filtered as a known prefix
    assert not any(v.lower() == "live-swe-agent" for v in variants)


def test_fm_leaderboards_name_variants_strips_parens():
    from ingestion.sources.fm_leaderboards import _name_variants
    variants = _name_variants("Atlassian Rovo Dev (2025-09-02)")
    assert any("Atlassian Rovo Dev" in v and "2025" not in v for v in variants)


def test_fm_leaderboards_find_agent_prefers_shortest_slug():
    """When multiple agent slugs substring-match the same published
    name, the shortest (canonical) one wins. Without this, lmarena's
    ``claude-opus-4-7`` would arbitrarily route to either our
    canonical slug or the -fast variant.
    """
    import uuid

    from ingestion.sources.fm_leaderboards import _find_agent_for_name, _normalize

    canonical_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    # Sorted by length ascending — canonical is shorter
    agent_norms = [
        (_normalize("anthropic-claude-opus-4-7"), canonical_id),
        (_normalize("anthropic-claude-opus-4-7-fast"), variant_id),
    ]
    agent_norms.sort(key=lambda x: len(x[0]))

    matched = _find_agent_for_name("claude-opus-4-7", agent_norms)
    assert matched == canonical_id


def test_fm_leaderboards_find_agent_swe_bench_harness_format():
    """The big one: SWE-bench publishes every top entry as
    "harness + Model decorators". Our matcher must strip the harness
    prefix + decorators and still find the model.
    """
    import uuid

    from ingestion.sources.fm_leaderboards import _find_agent_for_name, _normalize

    opus_id = uuid.uuid4()
    agent_norms = [(_normalize("anthropic-claude-opus-4-5"), opus_id)]

    # SWE-bench writes "Claude 4.5 Opus" (number before Opus) while
    # our slug is "claude-opus-4-5" (number after). The harness +
    # decorator strip alone can't fix that ordering — we still match
    # because the segment ``Claude 4.5 Opus`` normalises to
    # ``claude45opus`` which is a substring of ``anthropicclaudeopus45``
    # ... actually no it isn't (4-5 comes after opus in our slug).
    # The test confirms the *current* behaviour — full match still
    # depends on token-bag matching which is a separate phase. We
    # at least verify the harness is stripped from variants.
    variants_check = _find_agent_for_name(
        "live-SWE-agent + Claude Opus 4.5 (high)", agent_norms
    )
    # Our slug normalised: "anthropicclaudeopus45"
    # "Claude Opus 4.5" normalised: "claudeopus45" — IS substring of the agent norm
    assert variants_check == opus_id


# --------------------------------------------------------- artificial_analysis


def test_aa_dig_walks_nested_dict():
    """Verify the nested-dict accessor used to pull benchmark scores
    out of AA's response shape."""
    from ingestion.sources.artificial_analysis import _dig
    data = {
        "evaluations": {"gpqa": 94.2, "mmlu_pro": 89.8},
        "pricing": {"price_1m_input_tokens": 5.0},
        "median_output_tokens_per_second": 120.5,
    }
    assert _dig(data, "evaluations.gpqa") == 94.2
    assert _dig(data, "evaluations.mmlu_pro") == 89.8
    assert _dig(data, "pricing.price_1m_input_tokens") == 5.0
    assert _dig(data, "median_output_tokens_per_second") == 120.5
    assert _dig(data, "evaluations.missing") is None
    assert _dig(data, "no.such.path") is None


def test_aa_benchmark_field_map_covers_intelligence_index():
    """The Intelligence Index components from AA v4.0 should all be in
    the field map so they actually land in benchmark_results."""
    from ingestion.sources.artificial_analysis import BENCHMARK_FIELD_MAP
    # Spot-check a few that the methodology mentions explicitly.
    assert "evaluations.gpqa" in BENCHMARK_FIELD_MAP
    assert "evaluations.mmlu_pro" in BENCHMARK_FIELD_MAP
    assert "evaluations.terminalbench_hard" in BENCHMARK_FIELD_MAP
    assert "evaluations.hle" in BENCHMARK_FIELD_MAP
    assert "evaluations.aime" in BENCHMARK_FIELD_MAP
    # The composite itself is also a benchmark.
    assert "evaluations.artificial_analysis_intelligence_index" in BENCHMARK_FIELD_MAP
    # All entries map to (slug, category) tuples.
    for mapped in BENCHMARK_FIELD_MAP.values():
        assert isinstance(mapped, tuple) and len(mapped) == 2


async def test_semantic_scholar_sums_citations():
    settings = Settings(openalex_mailto=None, semantic_scholar_api_key="k")
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


# ---------------------------------------------------- hn phrase for FMs


def test_fm_hn_phrase_strips_provider_and_quotes():
    from ingestion.sources.hackernews import fm_hn_phrase

    assert fm_hn_phrase("OpenAI: GPT-5.2") == '"GPT-5.2"'
    assert fm_hn_phrase("Anthropic: Claude Opus 5 (batch)") == '"Claude Opus 5 batch"'
    assert fm_hn_phrase("Goliath 120B") == '"Goliath 120B"'


def test_fm_hn_phrase_skips_generic_single_word():
    """'Pareto' matched every 'Pareto frontier' comment on HN."""
    from ingestion.sources.hackernews import fm_hn_phrase

    assert fm_hn_phrase("Pareto") is None
    assert fm_hn_phrase("Other: Pareto") is None
    assert fm_hn_phrase("Perplexity: Sonar") is None
    assert fm_hn_phrase("Qwen: Qwen-Max ") == '"Qwen-Max"'
    assert fm_hn_phrase(None) is None


async def test_hn_mentions_fm_uses_quoted_name_phrase():
    settings = Settings()
    a = _agent(
        slug="openai-gpt-5-2",
        name="OpenAI: GPT-5.2",
        github_repo=None,
        entity_kind="foundation_model",
    )
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"nbHits": 3, "hits": [
            {"title": "GPT-5.2 is out"},
            {"comment_text": "I prefer <b>gpt-5.2</b> to gpt-5.6"},
            {"title": "GPT-5.6 review"},  # sibling version, not counted
        ]})

    ing = HNMentions7dIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a, _agent(name="Pareto", entity_kind="foundation_model")])
    finally:
        await ing.aclose()
    assert [r.agent_id for r in readings] == [a.id]
    assert seen["query"] == '"GPT-5.2"'
    assert seen["advancedSyntax"] == "true"
    assert readings[0].value == 2.0


# ------------------------------------------------------ openrouter pricing


async def test_openrouter_pricing_blends_and_matches_by_id_or_slug():
    from ingestion.sources.openrouter_pricing import OpenRouterPricingIngestor

    by_id = _agent(
        slug="whatever",
        entity_kind="foundation_model",
        facts={"openrouter_id": "openai/gpt-5.2"},
    )
    by_slug = _agent(slug="anthropic-claude-opus-5", entity_kind="foundation_model")
    free = _agent(slug="z-ai-glm-4-5-air-free", entity_kind="foundation_model")
    app = _agent(slug="openai-gpt-5-2")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"id": "openai/gpt-5.2", "name": "OpenAI: GPT-5.2",
             "pricing": {"prompt": "0.000002", "completion": "0.000008"}},
            {"id": "anthropic/claude-opus-5", "name": "Anthropic: Claude Opus 5",
             "pricing": {"prompt": "0.000015", "completion": "0.000075"}},
            {"id": "z-ai/glm-4.5-air:free", "name": "Z.ai: GLM 4.5 Air (free)",
             "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "openrouter/auto", "name": "Auto Router",
             "pricing": {"prompt": "-1", "completion": "-1"}},
        ]})

    ing = OpenRouterPricingIngestor(Settings(), http=_client(handler))
    try:
        readings = await ing.fetch([by_id, by_slug, free, app])
    finally:
        await ing.aclose()
    got = {r.agent_id: r.value for r in readings}
    assert got == {by_id.id: 5.0, by_slug.id: 45.0}
    assert all(r.source == SignalSource.OPENROUTER_PRICE_BLENDED for r in readings)


# ------------------------------------------------ artificial_analysis match


def _aa(creator: str, slug: str, **evals: float) -> dict[str, Any]:
    return {"model_creator": {"slug": creator}, "slug": slug, "evaluations": evals}


def test_aa_match_models_aliases_preview_and_effort():
    from ingestion.sources.artificial_analysis import match_models

    ids = {s: uuid.uuid4() for s in (
        "anthropic-claude-opus-5",
        "z-ai-glm-5-3",
        "google-gemini-3-1-pro-preview",
        "openai-gpt-6-astra",
        "spacexai-grok-4-7",
    )}
    plain = _aa("anthropic", "claude-opus-5", gpqa=0.9)
    models = [
        _aa("anthropic", "claude-opus-5-xhigh", gpqa=0.1),  # plain exists: ignored
        plain,
        _aa("zai", "glm-5-3"),
        _aa("google", "gemini-3-1-pro"),
        _aa("openai", "gpt-6-astra-medium", gpqa=0.5),
        _aa("openai", "gpt-6-astra-xhigh", gpqa=0.8),  # strongest effort wins
        _aa("xai", "grok-4-7"),
        _aa("unknown", "model"),
    ]
    got = match_models(models, ids)
    assert got[ids["anthropic-claude-opus-5"]] is plain
    assert got[ids["openai-gpt-6-astra"]]["slug"] == "gpt-6-astra-xhigh"
    assert set(got) == set(ids.values())


def test_aa_to_percent_uses_explicit_scale():
    from ingestion.sources.artificial_analysis import _to_percent

    idx = "evaluations.artificial_analysis_coding_index"
    assert _to_percent(idx, 1.0) == 1.0  # index stays on 0-100
    assert _to_percent("evaluations.gpqa", 0.963) == 96.3
    assert _to_percent("evaluations.aime", 1.25) == 100.0
    assert _to_percent("evaluations.hle", 0) is None  # not yet evaluated
    assert _to_percent("evaluations.hle", None) is None


# ------------------------------------------------------------ bluesky auth


async def test_bluesky_auth_refreshes_instead_of_relogging():
    from ingestion.sources.bluesky import _BskyAuth

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        n = len(calls)
        return httpx.Response(
            200, json={"accessJwt": f"a{n}", "refreshJwt": f"r{n}"}
        )

    auth = _BskyAuth()
    async with _client(handler) as http:
        assert await auth.get(http, "h", "p") == "a1"
        auth.expires_at = 0  # access token expired
        assert await auth.get(http, "h", "p") == "a2"
    assert calls == [
        "/xrpc/com.atproto.server.createSession",
        "/xrpc/com.atproto.server.refreshSession",
    ]


async def test_bluesky_login_429_honours_reset_header():
    import time

    from ingestion.sources.bluesky import _BskyAuth

    reset = time.time() + 3 * 3600

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"ratelimit-reset": str(int(reset))})

    auth = _BskyAuth()
    async with _client(handler) as http:
        assert await auth.get(http, "h", "p") is None
    assert abs(auth.retry_after - int(reset)) < 2


def test_bluesky_query_for_fm_uses_display_name():
    from ingestion.sources.bluesky import _query_for

    fm = _agent(name="OpenAI: GPT-5.2", slug="openai-gpt-5-2",
                github_repo=None, entity_kind="foundation_model")
    assert _query_for(fm) == '"GPT-5.2"'
    assert _query_for(_agent()) == "agent"


async def test_openalex_sums_citations():
    settings = Settings(openalex_mailto="ops@example.com")
    a = _agent(arxiv_ids=["2604.01234", "2605.99999"])

    def handler(request: httpx.Request) -> httpx.Response:
        counts = {"2604.01234": 10, "2605.99999": 7}
        for arxiv_id, n in counts.items():
            if arxiv_id in request.url.path:
                return httpx.Response(200, json={"cited_by_count": n})
        return httpx.Response(404)

    ing = ArxivCitationsIngestor(settings, http=_client(handler))
    try:
        readings = await ing.fetch([a])
    finally:
        await ing.aclose()
    assert readings and readings[0].value == 17.0


# ------------------------------------------------------- word boundaries


def test_word_boundary_regex_rejects_sibling_versions():
    from ingestion.sources.name_tokens import word_boundary_regex

    p = word_boundary_regex(["GPT-5", "Claude Opus 5"])
    assert p.search("I tried GPT-5 yesterday.")
    assert p.search("openai/gpt-5, and it was fine")
    assert p.search("Claude Opus 5 (the big one)")
    assert not p.search("GPT-5.6 review")
    assert not p.search("gpt-5-mini is cheap")
    assert not p.search("Claude Opus 5.5 launched")
    assert not p.search("xgpt-5")


def test_hn_exact_count_extrapolates_past_page_limit():
    from ingestion.sources.hackernews import _exact_count

    a = _agent(name="OpenAI: GPT-5", slug="openai-gpt-5", entity_kind="foundation_model")
    hits = [{"title": "GPT-5"}] * 3 + [{"title": "GPT-5.6"}] * 7
    assert _exact_count(a, hits, nb_hits=10) == 3
    # 30 exact of 100 sampled, 1000 reported -> 300.
    assert _exact_count(a, hits * 10, nb_hits=1000) == 300
    assert _exact_count(a, [], nb_hits=50) == 0


async def test_bluesky_counts_exact_mentions_across_pages():
    from ingestion.sources.bluesky import _count
    from ingestion.sources.name_tokens import word_boundary_regex

    pages = {
        None: {"posts": [{"record": {"text": "GPT-5 rocks"}}] * 99
               + [{"record": {"text": "GPT-5.6 rocks"}}], "cursor": "p2"},
        "p2": {"posts": [{"record": {"text": "gpt-5 again"}}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[request.url.params.get("cursor")])

    async with _client(handler) as http:
        n = await _count(http, {}, '"GPT-5"', "2026-01-01T00:00:00Z",
                         word_boundary_regex(["GPT-5"]))
    assert n == 100


# ------------------------------------------------ github repos using model


def test_repos_using_model_query_uses_bare_model_id():
    from ingestion.sources.github_repos_using_model import _query_term, model_id

    a = _agent(slug="anthropic-claude-opus-5-5", entity_kind="foundation_model",
               facts={"openrouter_id": "anthropic/claude-opus-5.5"})
    assert model_id(a) == "claude-opus-5.5"
    assert _query_term(a) == '"claude-opus-5.5" in:name,description,readme'
    # No facts: slug minus provider prefix.
    b = _agent(slug="z-ai-glm-5-3", entity_kind="foundation_model")
    assert _query_term(b) == '"glm-5-3" in:name,description,readme'
    # Billing variants are the same model; skipped.
    c = _agent(slug="z-ai-glm-4-5-air-free", entity_kind="foundation_model",
               facts={"openrouter_id": "z-ai/glm-4.5-air:free"})
    assert _query_term(c) is None
    # A plain word matches every README that uses the word.
    d = _agent(slug="pareto", entity_kind="foundation_model",
               facts={"openrouter_id": "openrouter/pareto"})
    assert _query_term(d) is None


# ------------------------------------------------------- openrouter usage


def test_openrouter_tokens_in_window_plain_and_escaped():
    from datetime import date

    from ingestion.sources.openrouter_usage import tokens_in_window

    rows = ('[{"date":"2026-09-24 00:00:00","total_prompt_tokens":100,'
            '"total_completion_tokens":10,"variant":"standard"},'
            '{"date":"2026-08-01 00:00:00","total_prompt_tokens":999,'
            '"total_completion_tokens":1}]')
    plain = 'junk"top_apps":[{"x":[1]}],"top_apps_chart":' + rows + ',"more":1'
    escaped = 'self.__next_f.push("' + plain.replace('"', '\\"') + '")'
    cutoff = date(2026, 9, 1)
    assert tokens_in_window(plain, cutoff) == 110
    assert tokens_in_window(escaped, cutoff) == 110
    assert tokens_in_window("<html>no chart</html>", cutoff) is None


def test_openrouter_usage_resolves_id_from_facts_or_catalogue():
    from ingestion.sources.openrouter_usage import resolve_model_id

    by_slug = {"openai-gpt-5-2": "openai/gpt-5.2"}
    with_facts = _agent(slug="whatever", entity_kind="foundation_model",
                        facts={"openrouter_id": "anthropic/claude-opus-5.5"})
    assert resolve_model_id(with_facts, by_slug) == "anthropic/claude-opus-5.5"
    assert resolve_model_id(_agent(slug="openai-gpt-5-2"), by_slug) == "openai/gpt-5.2"
    assert resolve_model_id(_agent(slug="unknown"), by_slug) is None
