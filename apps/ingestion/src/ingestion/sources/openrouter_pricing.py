"""openrouter_price_blended — Efficiency pillar cost input for foundation models.

OpenRouter's public ``/api/v1/models`` lists per-token prompt and
completion prices for every model it serves. We store the blended
price (mean of input and output, in $ per million tokens), which the
scorer maps through an inverse log anchor (cheaper = higher).

This replaced Artificial Analysis as the price source: AA only covers
the models it benchmarks, so most of the board sat Unrated on
Efficiency even when a price was public.

Match: ``facts["openrouter_id"]`` first. Retention used to strip the
facts payload, so fall back to the slug the promoter derives from the
OpenRouter display name (``"OpenAI: GPT-5.2"`` → ``openai-gpt-5-2``).

Free (price 0) and router (price -1) entries are skipped: a zero price
isn't a serving-cost measurement, and scoring it as 100 would put every
``:free`` variant at the top of Efficiency.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, ClassVar, cast

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

MODELS = "https://openrouter.ai/api/v1/models"

# Same rule as discovery.promoter._make_slug.
_SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG_NONALNUM.sub("-", name.lower()).strip("-")[:100]


def _blended_per_million(pricing: dict[str, Any]) -> float | None:
    try:
        # float(None) raises TypeError, handled below.
        prompt = float(cast(Any, pricing.get("prompt")))
        completion = float(cast(Any, pricing.get("completion")))
    except (TypeError, ValueError):
        return None
    if prompt <= 0 or completion <= 0:
        return None
    return (prompt + completion) / 2.0 * 1_000_000


class OpenRouterPricingIngestor(Ingestor):
    name: ClassVar[str] = "openrouter_price_blended"
    source: ClassVar[SignalSource] = SignalSource.OPENROUTER_PRICE_BLENDED
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        try:
            r = await self._http.get(MODELS, timeout=30.0)
        except Exception as e:  # noqa: BLE001
            log.info("openrouter models fetch failed: %s", e)
            return []
        if r.status_code != 200:
            log.info("openrouter models returned %d", r.status_code)
            return []
        try:
            items = (r.json() or {}).get("data") or []
        except ValueError:
            return []

        by_id: dict[str, float] = {}
        by_slug: dict[str, float] = {}
        for m in items:
            price = _blended_per_million(m.get("pricing") or {})
            if price is None:
                continue
            if m.get("id"):
                by_id[m["id"].lower()] = price
            if m.get("name"):
                by_slug[_slug(m["name"])] = price

        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            if a.entity_kind != "foundation_model":
                continue
            or_id = (a.facts or {}).get("openrouter_id") if a.facts else None
            price = by_id.get(or_id.lower()) if isinstance(or_id, str) else None
            if price is None:
                price = by_slug.get(a.slug.lower())
            if price is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.OPENROUTER_PRICE_BLENDED,
                    value=round(price, 6),
                    captured_at=captured,
                )
            )
        return out
