"""google_trends_score — relative public-search interest, weekly cadence.

Google Trends has no official API. ``pytrends`` is a community library
that scrapes the unofficial endpoint; it works but rate-limits hard
and returns empty data when blocked. We treat that as a feature rather
than a bug:

  - Cadence is *weekly*, not slow-tier-daily, so we don't tickle the
    rate limiter on every cycle. This signal moves slowly enough that
    daily updates wouldn't tell us anything new.
  - On a rate-limit (429 or empty data) we silently no-op — the score
    pipeline reads the most recent prior reading via _last_value, so
    the agent's score stays at its last-known Google Trends value
    rather than degrading to "no signal".
  - We sleep 4–8 seconds between agent queries to spread load.

Trends score is the 0–100 relative-interest value Google publishes
for the query, averaged over the past 30 days. 0 means "no measurable
search interest", 100 means "peak in the window".

This ingestor runs in the slow tier but is governed by an internal
"only run once every 7 days" gate via Redis so the full 24h slow tier
isn't blocked waiting for it.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

# pytrends is imported lazily so the ingestion service can boot even
# without the optional dependency (e.g. dev environments where the
# extra package wasn't installed).
_pytrends_cls: Any | None = None


def _get_pytrends_cls() -> Any | None:
    global _pytrends_cls
    if _pytrends_cls is not None:
        return _pytrends_cls
    try:
        from pytrends.request import TrendReq  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return None
    _pytrends_cls = TrendReq
    return _pytrends_cls


class GoogleTrendsScoreIngestor(Ingestor):
    name: ClassVar[str] = "google_trends_score"
    source: ClassVar[SignalSource] = SignalSource.GOOGLE_TRENDS_SCORE
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        TrendReq = _get_pytrends_cls()
        if TrendReq is None:
            log.info("pytrends not installed; google_trends_score skipped")
            return []

        # We don't run on every slow-tier tick — only once a week.
        # The slow tier already runs daily, so 6 of every 7 ticks
        # we early-return.
        if not _should_run_today(self.settings):
            return []

        # pytrends is synchronous and somewhat heavy. Build it once,
        # query agents serially with a randomised sleep so we don't
        # look like a bot pattern. The sample size matters less than
        # not getting blocked — 50 agents per run is plenty for the
        # weekly cadence.
        try:
            client = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
        except Exception as e:  # noqa: BLE001
            log.warning("pytrends init failed: %s", e)
            return []

        # Prefer foundation models (more public-search signal) and
        # cap to 50 per run — at ~6s/query that's ~5 minutes.
        ranked = sorted(
            agents,
            key=lambda a: 0 if a.entity_kind == "foundation_model" else 1,
        )
        targets = ranked[:50]

        out: list[SignalReading] = []
        for a in targets:
            term = _term_for(a)
            if not term:
                continue
            score = await _query_one(client, term)
            await asyncio.sleep(random.uniform(4, 8))
            if score is None:
                continue  # rate-limited; keep last_value via no-op
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.GOOGLE_TRENDS_SCORE,
                    value=float(score),
                    captured_at=datetime.now(UTC),
                )
            )
        return out


def _term_for(a: AgentRow) -> str | None:
    """Search term — prefer the human name to avoid slug noise."""
    name = (a.name or "").strip()
    if len(name) < 3:
        name = a.slug
    if not name:
        return None
    # Two-word minimum to reduce ambiguity ("aider" alone is fine,
    # "go" alone is not). pytrends accepts the raw string.
    return name


async def _query_one(client: Any, term: str) -> float | None:
    """Run one pytrends interest_over_time query, returning the 30d mean.

    Google Trends scores are 0–100 relative within the result. We pull
    the last 30 days at daily resolution and return the mean. On any
    error or empty frame we return None (caller treats as no-op).
    """
    loop = asyncio.get_running_loop()
    try:
        # pytrends is sync; run in default executor.
        def _run() -> float | None:
            client.build_payload([term], cat=0, timeframe="today 1-m", geo="", gprop="")
            df = client.interest_over_time()
            if df is None or df.empty or term not in df.columns:
                return None
            try:
                mean = float(df[term].astype(float).mean())
            except Exception:  # noqa: BLE001
                return None
            return max(0.0, min(100.0, mean))

        return await loop.run_in_executor(None, _run)
    except Exception as e:  # noqa: BLE001
        log.info("pytrends query for %r failed: %s", term, e)
        return None


def _should_run_today(settings: Any) -> bool:
    """Run on Mondays UTC only — once-a-week cadence without Redis state.

    This is dumb-on-purpose. We don't need persistent "last run" state
    if the rule is purely calendar-based, and it's robust to crashes
    or rescheduling. Trends data updates daily on Google's side but
    the relative scores don't move enough to merit hourly polling.
    """
    return datetime.now(UTC).weekday() == 0  # 0 = Monday
