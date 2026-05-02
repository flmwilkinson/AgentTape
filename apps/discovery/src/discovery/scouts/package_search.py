"""Package-manager scout (npm + PyPI).

Daily query of npm and PyPI for packages whose name or description matches
agent-keyword patterns; cross-references each to a GitHub repo when one is
declared in the package metadata.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import ClassVar

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)

NPM_SEARCH = "https://registry.npmjs.org/-/v1/search"
PYPI_JSON = "https://pypi.org/pypi/{name}/json"

# PyPI's search endpoint isn't public anymore. We instead cross-reference
# a curated keyword list of known agent-shaped package patterns; the
# scout fetches metadata for each match and decides whether to admit.
NPM_QUERIES: list[str] = [
    "ai-agent",
    "llm-agent",
    "agentic",
    "mcp-server",
    "browser-agent",
    "autonomous-agent",
]
# These are the "namespace" hints — packages starting with these prefixes
# or containing these substrings are worth inspecting.
PYPI_CANDIDATES: list[str] = [
    "langchain",
    "crewai",
    "autogen-agentchat",
    "autogen",
    "llama-agents",
    "smol-agents",
    "smolagents",
    "agency-swarm",
    "multion",
    "browser-use",
    "openhands-ai",
    "swe-agent",
    "metagpt",
    "agentops",
    "phidata",
    "praisonai",
    "agno",
]


class PackageSearchScout(Scout):
    name: ClassVar[str] = "package_search"
    interval_seconds: ClassVar[int] = 24 * 60 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        async for c in self._npm():
            yield c
        async for c in self._pypi():
            yield c

    async def _npm(self) -> AsyncIterator[Candidate]:
        for q in NPM_QUERIES:
            r = await self._http.get(NPM_SEARCH, params={"text": q, "size": 50})
            if r.status_code != 200:
                log.warning("npm search returned %d for %s", r.status_code, q)
                continue
            for obj in r.json().get("objects", []):
                pkg = obj.get("package") or {}
                name = pkg.get("name")
                if not name:
                    continue
                links = pkg.get("links") or {}
                yield Candidate(
                    source=DiscoverySource.NPM,
                    source_id=name,
                    raw_payload={
                        "name": name,
                        "description": pkg.get("description"),
                        "version": pkg.get("version"),
                        "keywords": pkg.get("keywords"),
                        "publisher": (pkg.get("publisher") or {}).get("username"),
                        "links": links,
                        "github_repo": _gh_from_links(links),
                        "discovered_query": q,
                    },
                )

    async def _pypi(self) -> AsyncIterator[Candidate]:
        for name in PYPI_CANDIDATES:
            r = await self._http.get(PYPI_JSON.format(name=name))
            if r.status_code != 200:
                continue
            data = r.json()
            info = data.get("info") or {}
            urls = info.get("project_urls") or {}
            yield Candidate(
                source=DiscoverySource.PYPI,
                source_id=name,
                raw_payload={
                    "name": name,
                    "summary": info.get("summary"),
                    "version": info.get("version"),
                    "license": info.get("license"),
                    "home_page": info.get("home_page"),
                    "project_urls": urls,
                    "github_repo": _gh_from_pypi(urls, info.get("home_page")),
                    "downloads": (data.get("urls") or [{}])[0].get("downloads"),
                },
            )


def _gh_from_links(links: dict) -> str | None:
    for key in ("repository", "homepage", "bugs"):
        v = (links.get(key) or "").lower()
        if "github.com/" in v:
            tail = v.split("github.com/", 1)[1].strip("/")
            parts = tail.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
    return None


def _gh_from_pypi(urls: dict, home_page: str | None) -> str | None:
    candidates = list(urls.values()) + ([home_page] if home_page else [])
    for v in candidates:
        if not v:
            continue
        if "github.com/" in v.lower():
            tail = v.split("github.com/", 1)[1].strip("/")
            parts = tail.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1].removesuffix('.git')}"
    return None
