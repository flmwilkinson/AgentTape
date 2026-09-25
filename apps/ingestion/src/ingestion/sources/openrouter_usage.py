"""openrouter_token_volume_30d — real-traffic adoption for foundation models.

OpenRouter routes a meaningful share of public LLM traffic. Token
volume there is the closest public proxy to "models people are
actually paying to call in production" — it routinely diverges from
benchmark rank in ways that benchmark scores alone can't catch.

There is no documented stats API, and the frontend endpoint this used
to read (``/api/frontend/models``) now returns 404. Each public model
page (``https://openrouter.ai/<id>``) still embeds the data behind the
usage chart it renders: ``top_apps_chart``, one row per day per
variant for the last ~31 days with ``total_prompt_tokens`` and
``total_completion_tokens``. We sum the last 30 days. A page is 1–2 MB,
so this runs on the SLOW tier, two pages at a time.

Match:
    ``facts["openrouter_id"]`` when present; otherwise the OpenRouter
    catalogue (``/api/v1/models``) matched by the slug the promoter
    derives from the display name, as ``openrouter_pricing`` does.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar

import httpx

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.openrouter_pricing import MODELS, _slug

log = logging.getLogger(__name__)

PAGE = "https://openrouter.ai/{model_id}"
WINDOW_DAYS = 30
CONCURRENCY = 2
# The chart data is only rendered for browser-like clients.
UA = "Mozilla/5.0 (compatible; AgentTape/1.0; +https://agenttape.com)"

_CHART_KEY = "top_apps_chart"


class OpenRouterTokenVolume30dIngestor(Ingestor):
    name: ClassVar[str] = "openrouter_token_volume_30d"
    source: ClassVar[SignalSource] = SignalSource.OPENROUTER_TOKEN_VOLUME_30D
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        fms = [a for a in agents if a.entity_kind == "foundation_model"]
        if not fms:
            return []
        by_slug = await _catalogue_by_slug(self._http)
        sem = asyncio.Semaphore(CONCURRENCY)
        captured = datetime.now(UTC)
        cutoff = (captured - timedelta(days=WINDOW_DAYS)).date()

        async def one(a: AgentRow) -> SignalReading | None:
            mid = resolve_model_id(a, by_slug)
            if not mid:
                return None
            async with sem:
                try:
                    r = await self._http.get(
                        PAGE.format(model_id=mid),
                        headers={"User-Agent": UA},
                        timeout=40.0,
                    )
                except Exception as e:  # noqa: BLE001
                    log.debug("openrouter page %s failed: %s", mid, e)
                    return None
                await asyncio.sleep(0.5)
            if r.status_code != 200:
                return None
            tokens = tokens_in_window(r.text, cutoff)
            if tokens is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
                value=float(tokens),
                captured_at=captured,
            )

        results = await asyncio.gather(*(one(a) for a in fms))
        out = [r for r in results if r is not None]
        log.info("openrouter usage: %d of %d models read", len(out), len(fms))
        return out


# ----------------------------------------------------------------- helpers


async def _catalogue_by_slug(http: httpx.AsyncClient) -> dict[str, str]:
    """Promoter-style slug -> OpenRouter id, for agents whose facts
    payload (and so ``openrouter_id``) is missing."""
    try:
        r = await http.get(MODELS, timeout=30.0)
        items = (r.json() or {}).get("data") or [] if r.status_code == 200 else []
    except Exception as e:  # noqa: BLE001
        log.info("openrouter catalogue fetch failed: %s", e)
        return {}
    out: dict[str, str] = {}
    for m in items:
        if isinstance(m, dict) and m.get("id") and m.get("name"):
            out.setdefault(_slug(str(m["name"])), str(m["id"]))
    return out


def resolve_model_id(a: AgentRow, by_slug: dict[str, str]) -> str | None:
    facts = a.facts or {}
    oid = facts.get("openrouter_id") if isinstance(facts, dict) else None
    if isinstance(oid, str) and oid.strip():
        return oid.strip()
    return by_slug.get((a.slug or "").lower())


def tokens_in_window(page: str, cutoff: date) -> int | None:
    """Prompt + completion tokens for chart days on or after ``cutoff``.

    None when the page carries no chart (unknown model, bot page,
    layout change) so the agent keeps its last reading. A chart with
    no rows in the window is a real zero.
    """
    rows = _chart_rows(page)
    if rows is None:
        return None
    total = 0
    for row in rows:
        try:
            day = date.fromisoformat(str(row.get("date") or "")[:10])
        except ValueError:
            continue
        if day < cutoff:
            continue
        total += int(row.get("total_prompt_tokens") or 0)
        total += int(row.get("total_completion_tokens") or 0)
    return total


def _chart_rows(page: str) -> list[dict[str, Any]] | None:
    # The chart sits in a serialised react-query cache. Depending on
    # where it lands in the RSC payload the JSON is either plain or
    # escaped inside a JS string (\"key\":[...]).
    for needle, escaped in (
        (f'"{_CHART_KEY}":[', False),
        (f'\\"{_CHART_KEY}\\":[', True),
    ):
        i = page.find(needle)
        if i < 0:
            continue
        blob = _balanced(page, page.index("[", i))
        if blob is None:
            return None
        try:
            if escaped:
                # The blob is the body of a JSON string: unescape it
                # the same way a JSON parser would.
                blob = json.loads(f'"{blob}"')
            rows = json.loads(blob)
        except ValueError:
            return None
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None
    return None


def _balanced(s: str, start: int) -> str | None:
    depth = 0
    for j in range(start, len(s)):
        c = s[j]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return s[start : j + 1]
    return None
