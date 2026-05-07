"""openrouter_token_volume_30d — real-traffic adoption for foundation models.

OpenRouter routes a meaningful share of public LLM traffic and
publishes per-model usage rankings on https://openrouter.ai/rankings.
Token volume there is the closest public proxy to "models people are
actually paying to call in production" — it routinely diverges from
benchmark rank in ways that benchmark scores alone can't catch.

Caveat: there is **no officially-documented public stats API**. We hit
``/api/frontend/models`` which is the same endpoint their UI uses; the
shape may shift. We treat any non-200, schema mismatch, or missing
field as "no data this tick" rather than crashing — the score formula
keeps the agent's last-known reading via ``_last_value`` so a temporary
endpoint outage doesn't decay the score.

Match:
    agent.entity_kind == "foundation_model" AND
    agent.facts["openrouter_id"] matches a row in the rankings response.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

# Frontend stats endpoint used by openrouter.ai/rankings. Returns the
# full model list with usage ranking-adjacent fields. Not officially
# documented; treated as best-effort.
RANKINGS = "https://openrouter.ai/api/frontend/models"


class OpenRouterTokenVolume30dIngestor(Ingestor):
    name: ClassVar[str] = "openrouter_token_volume_30d"
    source: ClassVar[SignalSource] = SignalSource.OPENROUTER_TOKEN_VOLUME_30D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        rankings = await _fetch_rankings(self._http)
        if not rankings:
            return []

        # Build a lookup keyed by openrouter id (e.g. "openai/gpt-4o").
        # Each value is the 30-day token volume reported for that model.
        volume_by_or_id: dict[str, float] = {}
        for entry in rankings:
            or_id = (entry.get("slug") or entry.get("id") or "").strip()
            if not or_id:
                continue
            tokens = _extract_volume(entry)
            if tokens is None:
                continue
            # Aggregate across multiple variants (free / paid / context
            # length forks) by the canonical id stem so an agent slug
            # like ``openai/gpt-5`` picks up its full traffic regardless
            # of which variant the rankings split into.
            stem = or_id.split(":", 1)[0].lower()
            volume_by_or_id[stem] = volume_by_or_id.get(stem, 0.0) + tokens

        if not volume_by_or_id:
            log.info("openrouter rankings parsed but no usable rows")
            return []

        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            if a.entity_kind != "foundation_model":
                continue
            or_id = _agent_openrouter_id(a)
            if not or_id:
                continue
            value = volume_by_or_id.get(or_id.lower())
            if value is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.OPENROUTER_TOKEN_VOLUME_30D,
                    value=value,
                    captured_at=captured,
                )
            )
        return out


# ----------------------------------------------------------------- helpers


async def _fetch_rankings(http) -> list[dict[str, Any]] | None:
    """Hit the unofficial rankings endpoint, return the model list or None."""
    try:
        r = await http.get(RANKINGS, timeout=30.0)
    except Exception as e:  # noqa: BLE001
        log.info("openrouter rankings fetch failed: %s", e)
        return None
    if r.status_code != 200:
        log.info("openrouter rankings returned %d", r.status_code)
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    # Endpoint shape varies — accept either a top-level list or
    # {"data": [...]} / {"models": [...]}.
    if isinstance(data, list):
        return data
    for key in ("data", "models", "items"):
        v = data.get(key) if isinstance(data, dict) else None
        if isinstance(v, list):
            return v
    return None


def _extract_volume(entry: dict[str, Any]) -> float | None:
    """Pick the highest-priority volume-shaped field from an entry.

    OpenRouter has reshaped the field name several times. We try the
    most-likely candidates in priority order; if none match the entry
    is skipped silently.
    """
    candidates = (
        "tokens_30d",
        "total_tokens_30d",
        "weekly_tokens",
        "tokens_weekly",
        "total_tokens",
        "tokens",
    )
    for key in candidates:
        v = entry.get(key)
        if isinstance(v, (int, float)) and v >= 0:
            return float(v)
        if isinstance(v, dict):
            inner = v.get("total") or v.get("tokens")
            if isinstance(inner, (int, float)):
                return float(inner)
    return None


def _agent_openrouter_id(a: AgentRow) -> str | None:
    facts = a.facts or {}
    or_id = facts.get("openrouter_id") if isinstance(facts, dict) else None
    if isinstance(or_id, str) and or_id.strip():
        return or_id.strip()
    # Fall back to first hf_model_id where it matches the openrouter shape.
    for hf in a.hf_model_ids or []:
        if "/" in hf:
            return hf
    return None
