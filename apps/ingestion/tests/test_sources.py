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
