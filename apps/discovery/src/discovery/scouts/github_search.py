"""GitHub search scout.

Looks for AI-agent-shaped repos along three axes:

1. Free-text matches ("AI agent", "MCP server", ...) sorted by recently
   created and by most stars this week.
2. Topic tag matches (ai-agent, agentic-ai, mcp-server, ...).
3. Repos that depend on the major agent frameworks (langchain, crewai,
   autogen, llama-index, anthropic-sdk, openai). GitHub doesn't expose a
   "top dependents" API, so we use the dependency-graph proxy: search
   for code that imports those packages and rank by stars.

Dedupe key: ``source_id = repo_full_name``. The ON CONFLICT in the base
scout drops repeats from any of the three axes.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Free-text + topic queries.
TEXT_QUERIES: list[str] = [
    '"AI agent" in:description,readme',
    '"LLM agent" in:description,readme',
    '"agentic" in:description,readme',
    '"MCP server" in:description,readme',
]
TOPIC_TAGS: list[str] = [
    "ai-agent",
    "llm-agent",
    "autonomous-agent",
    "agentic-ai",
    "mcp-server",
    "ai-coding-agent",
    "browser-agent",
]
# We approximate "top dependents of langchain etc." by finding repos that
# import those packages and have nontrivial popularity.
DEPENDENT_QUERIES: list[str] = [
    "from langchain import",
    "from crewai import",
    "import autogen",
    "from llama_index",
    "from anthropic import",
    "from openai import OpenAI",
]


class GithubSearchScout(Scout):
    name: ClassVar[str] = "github_search"
    interval_seconds: ClassVar[int] = 30 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        # 1. Free-text matches, two sort orders each.
        last_week = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()
        for q in TEXT_QUERIES:
            async for c in self._search_repos(f"{q} created:>{last_week}", "created"):
                yield c
            async for c in self._search_repos(f"{q} pushed:>{last_week}", "stars"):
                yield c

        # 2. Topic tag matches.
        for tag in TOPIC_TAGS:
            async for c in self._search_repos(f"topic:{tag}", "stars"):
                yield c

        # 3. Dependents of agent frameworks (code search → repos).
        for q in DEPENDENT_QUERIES:
            async for c in self._search_code_to_repos(q):
                yield c

    # --- HTTP layer ----------------------------------------------------

    def _auth(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            h["Authorization"] = f"Bearer {self.settings.github_token}"
        return h

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.get(url, params=params, headers=self._auth())
        # Soft-fail on rate limits and on /search/code 401 (which fires when
        # GITHUB_TOKEN is missing — code search has always required auth).
        if r.status_code == 403 and "rate limit" in r.text.lower():
            log.warning("github rate limited: %s", r.text[:200])
            return {"items": []}
        if r.status_code == 401 and "/search/code" in url:
            log.info("github code search needs a token; skipping")
            return {"items": []}
        r.raise_for_status()
        return r.json()

    async def _search_repos(
        self, q: str, sort: str
    ) -> AsyncIterator[Candidate]:
        data = await self._get(
            f"{GITHUB_API}/search/repositories",
            {"q": q, "sort": sort, "order": "desc", "per_page": 30},
        )
        for repo in data.get("items", []):
            full_name = repo.get("full_name")
            if not full_name:
                continue
            yield Candidate(
                source=DiscoverySource.GITHUB,
                source_id=full_name,
                raw_payload={
                    "name": repo.get("name"),
                    "full_name": full_name,
                    "description": repo.get("description"),
                    "html_url": repo.get("html_url"),
                    "homepage": repo.get("homepage"),
                    "stargazers_count": repo.get("stargazers_count"),
                    "forks_count": repo.get("forks_count"),
                    "topics": repo.get("topics"),
                    "language": repo.get("language"),
                    "license": (repo.get("license") or {}).get("spdx_id"),
                    "pushed_at": repo.get("pushed_at"),
                    "created_at": repo.get("created_at"),
                    "open_issues_count": repo.get("open_issues_count"),
                    "discovered_query": q,
                    "discovered_sort": sort,
                },
            )

    async def _search_code_to_repos(self, q: str) -> AsyncIterator[Candidate]:
        # GitHub code search: returns code matches; the repo info nested in each.
        data = await self._get(
            f"{GITHUB_API}/search/code", {"q": q, "per_page": 30}
        )
        seen: set[str] = set()
        for hit in data.get("items", []):
            repo = hit.get("repository") or {}
            full_name = repo.get("full_name")
            if not full_name or full_name in seen:
                continue
            seen.add(full_name)
            yield Candidate(
                source=DiscoverySource.GITHUB,
                source_id=full_name,
                raw_payload={
                    "name": repo.get("name"),
                    "full_name": full_name,
                    "description": repo.get("description"),
                    "html_url": repo.get("html_url"),
                    "discovered_query": q,
                    "discovered_via": "code_search",
                },
            )
