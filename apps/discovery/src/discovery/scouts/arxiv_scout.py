"""arXiv scout.

Daily query against arXiv for new cs.AI / cs.CL papers mentioning
"agent" together with one of (framework | benchmark | release). We pull
the abstract and extract any github.com URLs — research papers are a
strong source of newly-published frameworks and benchmarks that
GitHub-trending hasn't caught yet.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from typing import ClassVar

import feedparser

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
GITHUB_RE = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)", re.IGNORECASE)

# arXiv search syntax: cat:cs.AI + (abs:agent AND (abs:framework OR abs:benchmark OR abs:release))
ARXIV_QUERY = (
    "(cat:cs.AI OR cat:cs.CL) AND "
    "abs:agent AND (abs:framework OR abs:benchmark OR abs:release)"
)


class ArxivScout(Scout):
    name: ClassVar[str] = "arxiv_scout"
    interval_seconds: ClassVar[int] = 24 * 60 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        r = await self._http.get(
            ARXIV_API,
            params={
                "search_query": ARXIV_QUERY,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": 100,
            },
        )
        if r.status_code != 200:
            log.warning("arxiv returned %d", r.status_code)
            return
        feed = feedparser.parse(r.text)
        for entry in feed.entries:
            arxiv_id = (entry.get("id") or "").rsplit("/", 1)[-1]
            if not arxiv_id:
                continue
            summary = (entry.get("summary") or "").replace("\n", " ")
            title = (entry.get("title") or "").replace("\n", " ")

            # Yield the paper itself as a candidate.
            yield Candidate(
                source=DiscoverySource.ARXIV,
                source_id=arxiv_id,
                raw_payload={
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "summary": summary,
                    "authors": [a.get("name") for a in (entry.get("authors") or [])],
                    "published": entry.get("published"),
                    "primary_category": (entry.get("arxiv_primary_category") or {}).get("term"),
                    "html_url": entry.get("link"),
                    "github_repos": list(_extract_github_repos(summary)),
                },
            )

            # And any GitHub repos referenced in the abstract — those are
            # the actual frameworks the paper releases.
            for owner, repo in _extract_github_repos(summary):
                full = f"{owner}/{repo}"
                yield Candidate(
                    source=DiscoverySource.GITHUB,
                    source_id=full,
                    raw_payload={
                        "full_name": full,
                        "discovered_via": "arxiv",
                        "arxiv_id": arxiv_id,
                        "title": title,
                    },
                )


def _extract_github_repos(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in GITHUB_RE.finditer(text or ""):
        repo = m.group(2).removesuffix(".git").rstrip(",.)")
        out.append((m.group(1), repo))
    return out
