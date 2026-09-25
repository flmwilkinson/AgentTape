"""Hacker News mention count over the last 7 days.

One Algolia call per agent isn't free but the count is small (one batch
per fast tier tick) and the API is generous. Applications search by
github_repo full name, falling back to slug, and take Algolia's hit
count. Foundation models search by their display name as an exact
phrase (see ``fm_hn_phrase``) and then count only the hits whose text
actually contains the model name at a word boundary — Algolia's phrase
match tokenises on punctuation, so ``"GPT-5"`` also returns every
GPT-5.2 / GPT-5.6 post (90 hits of which 3 were about GPT-5 when this
was checked) and every base version was credited with its successors'
conversation.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.name_tokens import fm_search_tokens, word_boundary_regex

log = logging.getLogger(__name__)

ALGOLIA = "https://hn.algolia.com/api/v1/search"
# Algolia's page-size ceiling. Models with more weekly mentions than
# this are extrapolated from the sampled ratio (see ``_exact_count``).
HITS_PAGE = 1000

_TAG = re.compile(r"<[^>]+>")


class HNMentions7dIngestor(Ingestor):
    name: ClassVar[str] = "hn_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.HN_MENTIONS_7D
    tier: ClassVar[str] = "fast"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        since = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
        # Throttle to be polite — Algolia rate-limits aggressive callers.
        sem = asyncio.Semaphore(4)

        async def one(a: AgentRow) -> SignalReading | None:
            params: dict[str, str | int] = {
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{since}",
                "hitsPerPage": 0,
            }
            is_fm = a.entity_kind == "foundation_model"
            if is_fm:
                term = fm_hn_phrase(a.name)
                # Honour the quoted phrase, and pull the text so we can
                # count exact mentions rather than trust nbHits.
                params["advancedSyntax"] = "true"
                params["hitsPerPage"] = HITS_PAGE
                params["attributesToRetrieve"] = "title,comment_text,story_text"
            else:
                term = a.github_repo or a.slug
            if not term:
                return None
            params["query"] = term
            async with sem:
                try:
                    r = await self._http.get(ALGOLIA, params=params)
                except Exception:  # noqa: BLE001
                    return None
            if r.status_code != 200:
                return None
            data = r.json() or {}
            nb_hits = data.get("nbHits")
            if nb_hits is None:
                return None
            if is_fm:
                count = _exact_count(a, data.get("hits") or [], int(nb_hits))
            else:
                count = int(nb_hits)
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.HN_MENTIONS_7D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


def fm_hn_phrase(name: str | None) -> str | None:
    """Quoted phrase people actually write for a foundation model.

    FM slugs ("openai-gpt-5-2") almost never appear on HN, so the old
    slug query read 0 for most flagships, while a one-word name like
    "Pareto" matched every "Pareto frontier" comment and topped
    Adoption. Use the display name minus its "Provider: " prefix, as
    an exact phrase. A single plain word ("Pareto", "Sonar") is too
    generic to attribute, so return None and leave the signal unrated;
    joined brand names like "Qwen-Max" are distinctive and kept.
    """
    if not name:
        return None
    clean = re.sub(r"^[^:]+:\s*", "", name)
    clean = re.sub(r"[()]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return None
    if re.fullmatch(r"[A-Za-z]+", clean):
        return None
    return f'"{clean}"'


def _hit_text(hit: dict[str, Any]) -> str:
    parts = (hit.get("title"), hit.get("comment_text"), hit.get("story_text"))
    raw = " ".join(p for p in parts if isinstance(p, str))
    return html.unescape(_TAG.sub(" ", raw))


def _exact_count(a: AgentRow, hits: list[dict[str, Any]], nb_hits: int) -> int:
    """Hits that mention the model itself, not a sibling version.

    When Algolia had more hits than it returned, scale the sampled
    exact-match ratio up to ``nb_hits`` rather than under-report.
    """
    if not hits:
        return 0
    pattern = word_boundary_regex(fm_search_tokens(a))
    matched = sum(1 for h in hits if pattern.search(_hit_text(h)))
    if nb_hits > len(hits):
        return round(matched * nb_hits / len(hits))
    return matched
