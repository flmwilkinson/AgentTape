"""news_mentions_30d — count of articles mentioning the agent across
a curated set of tech-news RSS feeds.

Distinct from ``hn_mentions_7d`` (which counts forum threads) and from
``wikipedia_views_30d`` (which counts page views). News mentions are
the closest public proxy for "is this a household name yet" — when
TechCrunch, the Verge, VentureBeat write about it, that's a different
adoption signal than a Hacker News post is.

Design choices:

* RSS feeds, not Google News API. Google deprecated the API; news
  aggregators behind paywalls (NewsAPI, MediaStack) cost money and
  this is a free-only project. RSS is what's left, and a handful of
  high-signal feeds capture the bulk of meaningful coverage.

* Slow-tier. Articles get republished and re-promoted across the day
  but the signal we're measuring is "is this in the news", which has
  a ~daily cadence. Hourly polling would just add noise.

* Word-boundary matching from ``name_tokens.search_tokens`` — same
  helper that benchmarks/arxiv use. Critical for FMs: "GPT-5"
  matches "GPT-5" the article wrote, not "openai-gpt-5" we store.
  Word boundaries avoid "gpt-5" eating "gpt-5-mini" mentions.

Limitation: RSS feeds typically expose only the most-recent ~50
articles, which means the 30d window is optimistic — older mentions
fall out of the feed. The signal still works directionally (a model
people have been writing about for the last month carries more
mentions than one they've forgotten), but absolute counts are
ceilinged by the feed's retention.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

import feedparser

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.name_tokens import search_tokens, word_boundary_regex

log = logging.getLogger(__name__)

# Feeds to scan. High-signal generalist tech press; deliberately not
# AI-only to keep the signal a real "household name" proxy rather
# than a re-statement of HN coverage. Easy to extend — drop another
# RSS URL into this tuple and the next slow-tier tick picks it up.
NEWS_FEEDS: tuple[str, ...] = (
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://venturebeat.com/feed/",
    "https://arstechnica.com/feed/",
    "https://www.technologyreview.com/feed/",
    # AI-focused secondary feeds that catch FM coverage the
    # generalists miss.
    "https://www.marktechpost.com/feed/",
    "https://syncedreview.com/feed/",
)


class NewsMentionsIngestor(Ingestor):
    name: ClassVar[str] = "news_mentions_30d"
    source: ClassVar[SignalSource] = SignalSource.NEWS_MENTIONS_30D
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # Pull every feed once. Concurrent because each is a different
        # host; bound to len(NEWS_FEEDS) which is small.
        async def grab(url: str) -> str | None:
            try:
                r = await self._http.get(url)
            except Exception as e:  # noqa: BLE001
                log.debug("news feed fetch failed %s: %s", url, e)
                return None
            if r.status_code != 200:
                return None
            return r.text

        feed_xmls = await asyncio.gather(*(grab(u) for u in NEWS_FEEDS))

        # Build a flat corpus — one (title + summary) per article. We
        # don't need to know which feed an article came from for the
        # signal, just whether the agent's tokens appear anywhere in
        # the corpus.
        articles: list[str] = []
        for xml in feed_xmls:
            if not xml:
                continue
            parsed = feedparser.parse(xml)
            for entry in parsed.entries:
                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or ""
                articles.append(f"{title} {summary}")

        if not articles:
            log.warning("news_mentions: no articles fetched from any feed")
            return []

        # One pass per agent: build the word-boundary regex from the
        # canonical token list and count matching articles.
        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            tokens = search_tokens(a)
            if not tokens:
                continue
            pattern = word_boundary_regex(tokens)
            count = sum(1 for art in articles if pattern.search(art))
            # Only emit a reading when we actually saw something —
            # writing zero readings every tick would clutter the
            # signals table without adding information. The breakdown
            # panel already shows "Awaiting first reading" for
            # missing data.
            if count == 0:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.NEWS_MENTIONS_30D,
                    value=float(count),
                    captured_at=captured,
                )
            )
        return out
