"""Hacker News firehose scout.

Hits HN Algolia for recent stories that link to a github.com URL whose
linked repo has agent-ish keywords. Launch-day diffusion is the whole
point: we want the agent in the index the day it's posted, not a week
later when GitHub has caught up.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)

ALGOLIA = "https://hn.algolia.com/api/v1/search_by_date"

AGENT_KEYWORDS = re.compile(
    r"\b(agent|agents|agentic|llm|mcp|copilot|autonomous|tool[- ]?use|browser[- ]?use)\b",
    re.IGNORECASE,
)
GITHUB_RE = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)", re.IGNORECASE)


class HNFirehoseScout(Scout):
    name: ClassVar[str] = "hn_firehose"
    interval_seconds: ClassVar[int] = 5 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        # Last 24h. The 5-min cadence means most calls return only a
        # handful of new stories; the wider window catches anything
        # missed during downtime.
        since = int((datetime.now(UTC) - timedelta(hours=24)).timestamp())

        for query in ("agent", "agentic", "MCP", '"AI agent"', '"LLM agent"'):
            r = await self._http.get(
                ALGOLIA,
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{since}",
                    "hitsPerPage": 100,
                },
            )
            if r.status_code != 200:
                log.warning("hn algolia returned %d", r.status_code)
                continue
            for hit in r.json().get("hits", []):
                async for c in self._candidates_from_hit(hit):
                    yield c

    async def _candidates_from_hit(self, hit: dict) -> AsyncIterator[Candidate]:
        title = hit.get("title") or ""
        url = hit.get("url") or ""
        story_text = hit.get("story_text") or ""

        # Two paths: (a) the story links directly to a github repo whose
        # context looks agent-ish, or (b) the story body mentions a repo
        # and AGENT_KEYWORDS appear anywhere.
        repos: set[tuple[str, str]] = set()
        for blob in (url, story_text, title):
            for m in GITHUB_RE.finditer(blob or ""):
                owner, repo = m.group(1), m.group(2).removesuffix(".git")
                repos.add((owner, repo))

        if not repos:
            return
        # Need at least one mention of an agent keyword in title/body
        # to suppress generic CRUD-app submissions.
        if not AGENT_KEYWORDS.search(title + " " + story_text):
            return

        for owner, repo in repos:
            full_name = f"{owner}/{repo}"
            yield Candidate(
                source=DiscoverySource.HACKER_NEWS,
                source_id=f"{hit.get('objectID')}:{full_name}",
                raw_payload={
                    "hn_id": hit.get("objectID"),
                    "hn_title": title,
                    "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "story_url": url,
                    "story_text": story_text[:2000] if story_text else None,
                    "github_repo": full_name,
                    "points": hit.get("points"),
                    "num_comments": hit.get("num_comments"),
                    "created_at": hit.get("created_at"),
                },
            )
