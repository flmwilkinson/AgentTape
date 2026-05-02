"""Scout parsing tests.

Each scout gets a fake httpx transport that returns canned API responses.
We verify the scout produces well-formed Candidate objects with the right
``source``, ``source_id``, and key payload fields. No network.

Live recording-based tests live in ``test_scouts_live.py`` and use VCR
cassettes — they are tagged ``@pytest.mark.live`` and skipped by default.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from discovery.config import Settings
from discovery.enums import DiscoverySource
from discovery.scouts.arxiv_scout import ArxivScout
from discovery.scouts.github_search import GithubSearchScout
from discovery.scouts.hf_trending import HFTrendingScout
from discovery.scouts.hn_firehose import HNFirehoseScout
from discovery.scouts.mcp_registries import MCPRegistriesScout
from discovery.scouts.package_search import PackageSearchScout

pytestmark = pytest.mark.asyncio


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )


async def _collect(scout) -> list:
    out = []
    async for c in scout.discover():
        out.append(c)
    return out


# ---------------------------------------------------------------- github


async def test_github_search_yields_candidates_for_repo_search():
    settings = Settings(github_token=None, max_candidates_per_run=10)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/search/repositories" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "full_name": "anthropics/agent-toolkit",
                            "name": "agent-toolkit",
                            "description": "An AI agent toolkit",
                            "html_url": "https://github.com/anthropics/agent-toolkit",
                            "stargazers_count": 1234,
                            "forks_count": 56,
                            "topics": ["ai-agent", "llm"],
                            "language": "Python",
                            "license": {"spdx_id": "MIT"},
                            "pushed_at": "2026-04-30T00:00:00Z",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        if "/search/code" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "repository": {
                                "full_name": "user/cool-agent",
                                "name": "cool-agent",
                                "description": "Uses langchain",
                                "html_url": "https://github.com/user/cool-agent",
                            }
                        }
                    ]
                },
            )
        return httpx.Response(404)

    scout = GithubSearchScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    assert any(c.source_id == "anthropics/agent-toolkit" for c in cands)
    assert any(c.source_id == "user/cool-agent" for c in cands)
    assert all(c.source == DiscoverySource.GITHUB for c in cands)


async def test_github_search_soft_fails_on_rate_limit():
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            text="API rate limit exceeded",
        )

    scout = GithubSearchScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()
    # Soft fail returns no candidates but does not raise.
    assert cands == []


# ---------------------------------------------------------------- hf


async def test_hf_trending_filters_to_agent_tags():
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "anthropic/claude-agents",
                    "tags": ["agents", "tool-use"],
                    "downloads": 5000,
                    "likes": 100,
                    "trendingScore": 99,
                    "lastModified": "2026-04-30T00:00:00Z",
                },
                {
                    "id": "some/random-model",
                    "tags": ["text-classification"],
                    "downloads": 100,
                },
            ],
        )

    scout = HFTrendingScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    sids = {c.source_id for c in cands}
    # The agent-tagged model is yielded for both the model and space endpoints.
    assert "model:anthropic/claude-agents" in sids
    assert "space:anthropic/claude-agents" in sids
    # The non-agent model is filtered out.
    assert all("random-model" not in s for s in sids)


# --------------------------------------------------------------- mcp


async def test_mcp_registries_yields_from_both_official_and_glama():
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if "registry.modelcontextprotocol.io" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "servers": [
                        {
                            "name": "filesystem",
                            "description": "MCP filesystem server",
                            "repository": "https://github.com/modelcontextprotocol/servers",
                        }
                    ],
                    "metadata": {"next_cursor": None},
                },
            )
        if "glama.ai" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "servers": [
                        {
                            "slug": "github-server",
                            "name": "GitHub MCP",
                            "description": "GitHub MCP server",
                            "tags": ["dev"],
                        }
                    ]
                },
            )
        return httpx.Response(404)

    scout = MCPRegistriesScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    sids = {c.source_id for c in cands}
    assert "official:filesystem" in sids
    assert "glama:github-server" in sids


# --------------------------------------------------------------- hn


async def test_hn_firehose_extracts_github_repos_and_requires_agent_keywords():
    settings = Settings()

    payload = {
        "hits": [
            {
                "objectID": "111",
                "title": "Show HN: A new browser-use agent",
                "url": "https://github.com/foo/browser-agent",
                "story_text": "We built an autonomous agent that uses tools.",
                "points": 200,
                "num_comments": 50,
                "created_at": "2026-04-30T10:00:00Z",
            },
            {
                "objectID": "222",
                "title": "Random post",
                "url": "https://github.com/foo/random-thing",
                "story_text": "Just a regular CRUD app.",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scout = HNFirehoseScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    sids = {c.source_id for c in cands}
    assert any("foo/browser-agent" in s for s in sids)
    assert all("foo/random-thing" not in s for s in sids)


# --------------------------------------------------------------- arxiv


async def test_arxiv_scout_emits_paper_and_referenced_repos():
    settings = Settings()

    atom = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2604.01234</id>
        <title>Toolformer: a new agent framework</title>
        <summary>We release a new agent framework. Code: https://github.com/example/toolformer .</summary>
        <published>2026-04-30T00:00:00Z</published>
        <link href="http://arxiv.org/abs/2604.01234"/>
      </entry>
    </feed>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=atom)

    scout = ArxivScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    sids = {c.source_id for c in cands}
    assert "2604.01234" in sids
    assert "example/toolformer" in sids


# -------------------------------------------------------- package_search


async def test_package_search_npm_and_pypi():
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if "registry.npmjs.org" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "objects": [
                        {
                            "package": {
                                "name": "agentic-toolkit",
                                "description": "Agentic toolkit for browsers",
                                "version": "0.1.0",
                                "keywords": ["agent", "ai"],
                                "links": {
                                    "repository": "https://github.com/foo/agentic-toolkit"
                                },
                            }
                        }
                    ]
                },
            )
        if "pypi.org" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "info": {
                        "summary": "An agent",
                        "version": "1.0",
                        "license": "MIT",
                        "home_page": "https://github.com/foo/crewai",
                        "project_urls": {
                            "Source": "https://github.com/foo/crewai"
                        },
                    }
                },
            )
        return httpx.Response(404)

    scout = PackageSearchScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()

    by_source = {c.source: c for c in cands}
    assert DiscoverySource.NPM in by_source
    assert by_source[DiscoverySource.NPM].source_id == "agentic-toolkit"
    assert any(c.source == DiscoverySource.PYPI for c in cands)


# ---------------------------------------------------------------- payload


async def test_candidate_payload_is_json_serializable():
    """Payloads round-trip through JSON because base.py stores them as JSONB."""
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if "/search/repositories" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "full_name": "x/y",
                            "stargazers_count": 1,
                            "topics": ["a"],
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"items": []})

    scout = GithubSearchScout(settings, http=_client(handler))
    cands = await _collect(scout)
    await scout.aclose()
    for c in cands:
        json.dumps(c.raw_payload)  # would raise on a non-serializable type
