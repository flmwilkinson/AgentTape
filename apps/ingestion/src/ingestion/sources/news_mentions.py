"""news_mentions_30d — count of news articles mentioning the agent
across the GDELT global news index, with a curated RSS scan as a
fallback when GDELT is unreachable.

Why GDELT primary:
    The GDELT Project indexes ~150,000 news outlets worldwide,
    every 15 minutes, and exposes a free public API with no key.
    The previous RSS-only implementation was bottlenecked by the
    seven feeds we'd hand-picked — TechCrunch, Verge, VentureBeat,
    Ars Technica, MIT Tech Review, MarkTechPost, Synced — which is
    a tiny slice of the actual press coverage. Switching to GDELT
    turns "what TechCrunch wrote" into "what every English-language
    news outlet wrote".

Why RSS as fallback:
    GDELT's DOC API has occasional outages and per-IP soft limits.
    When a GDELT call fails for an agent, we fall back to scanning
    the seven feed corpus we built earlier so the signal still
    populates with a degraded reading rather than going to zero.

Endpoint shape:
    GET https://api.gdeltproject.org/api/v2/doc/doc
        ?query="<token>"
        &mode=ArtList
        &maxrecords=250
        &format=json
        &timespan=30d
        &sort=hybridrel

    Response: {"articles": [{"url": ..., "seendate": ..., "domain": ...}, ...]}
    Article count = signal value, capped at 250 (GDELT max).

Rate limits:
    GDELT documents an informal limit of ~5 queries per second.
    With ~600 admitted agents, a single sweep is ~120 seconds —
    fine for slow tier.

Schedule: slow tier. Article counts at the day level don't move
faster than that, and the RSS feed contents only refresh every
~30 minutes anyway.
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

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MAX = 250  # the API caps records returned per query at 250

# RSS feeds for the fallback path. Same set we used before GDELT was
# wired in — generalist tech press that captures the household-name
# signal even when GDELT is down. Easy to extend.
NEWS_FEEDS: tuple[str, ...] = (
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://venturebeat.com/feed/",
    "https://arstechnica.com/feed/",
    "https://www.technologyreview.com/feed/",
    "https://www.marktechpost.com/feed/",
    "https://syncedreview.com/feed/",
    # Added in the GDELT batch — broader generalist coverage so
    # the fallback path matches the GDELT primary's intent.
    "https://www.wired.com/feed/rss",
    "https://www.404media.co/feed",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://spectrum.ieee.org/feeds/feed.rss",
)


class NewsMentionsIngestor(Ingestor):
    name: ClassVar[str] = "news_mentions_30d"
    source: ClassVar[SignalSource] = SignalSource.NEWS_MENTIONS_30D
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # Try GDELT first. If the *whole* GDELT path errors (network
        # blip, 5xx, rate-limit), we fall through to the RSS scan
        # for the entire batch rather than per-agent — one error
        # signal usually means the whole API is unhappy.
        gdelt_ok = True
        sem = asyncio.Semaphore(4)  # ~4 concurrent ≈ 4 q/s, just under GDELT's soft limit

        async def gdelt_count(term: str) -> int | None:
            params = {
                "query": term,
                "mode": "ArtList",
                "maxrecords": str(GDELT_MAX),
                "format": "json",
                "timespan": "30d",
                "sort": "hybridrel",
            }
            try:
                async with sem:
                    r = await self._http.get(
                        GDELT_DOC_URL, params=params, timeout=8.0
                    )
            except Exception as e:  # noqa: BLE001
                log.debug("gdelt fetch failed: %s", e)
                return None
            if r.status_code != 200:
                return None
            try:
                data = r.json()
            except Exception:  # noqa: BLE001
                return None
            articles = data.get("articles")
            if articles is None:
                # Empty result is reported as missing key, not [].
                return 0
            return len(articles)

        # Build queries up-front so the fallback path can re-use the
        # same token list without re-deriving.
        per_agent_terms: dict[str, str] = {}
        for a in agents:
            tokens = search_tokens(a)
            if not tokens:
                continue
            # GDELT supports OR with explicit ``OR``; keep it short
            # to avoid query-length issues.
            ored = " OR ".join(f'"{t}"' for t in tokens[:3])
            per_agent_terms[str(a.id)] = ored

        # GDELT primary pass.
        primary: dict[str, int] = {}
        if per_agent_terms:
            try:
                results = await asyncio.gather(
                    *(gdelt_count(term) for term in per_agent_terms.values()),
                    return_exceptions=True,
                )
                # If every call failed (all None or all exceptions),
                # treat GDELT as down and fall back.
                got_any = any(
                    isinstance(r, int) for r in results
                )
                if not got_any:
                    gdelt_ok = False
                    log.warning(
                        "news_mentions: GDELT returned nothing for %d agents — falling back to RSS",
                        len(per_agent_terms),
                    )
                else:
                    for (aid, _term), result in zip(
                        per_agent_terms.items(), results
                    ):
                        if isinstance(result, int):
                            primary[aid] = result
            except Exception as e:  # noqa: BLE001
                gdelt_ok = False
                log.warning("news_mentions: GDELT batch errored: %s", e)

        # RSS fallback for agents GDELT didn't answer.
        rss_corpus: list[str] | None = None
        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            aid = str(a.id)
            count: int | None = primary.get(aid)
            if count is None and not gdelt_ok:
                # Lazy-load the RSS corpus only when fallback is
                # needed.
                if rss_corpus is None:
                    rss_corpus = await _load_rss_corpus(self._http)
                if rss_corpus:
                    tokens = search_tokens(a)
                    if tokens:
                        pattern = word_boundary_regex(tokens)
                        count = sum(
                            1 for art in rss_corpus if pattern.search(art)
                        )
            if count is None or count == 0:
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


async def _load_rss_corpus(http) -> list[str]:
    async def grab(url: str) -> str | None:
        try:
            r = await http.get(url, timeout=8.0)
        except Exception as e:  # noqa: BLE001
            log.debug("news rss fetch failed %s: %s", url, e)
            return None
        if r.status_code != 200:
            return None
        return r.text

    feed_xmls = await asyncio.gather(*(grab(u) for u in NEWS_FEEDS))
    articles: list[str] = []
    for xml in feed_xmls:
        if not xml:
            continue
        parsed = feedparser.parse(xml)
        for entry in parsed.entries:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            articles.append(f"{title} {summary}")
    return articles
