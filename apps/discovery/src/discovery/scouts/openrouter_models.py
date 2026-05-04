"""Foundation-model scout — openrouter.ai/api/v1/models.

OpenRouter publishes the most-comprehensive free listing of public LLMs.
No auth, no rate limit at our scale, single endpoint, structured JSON.

Each entry produces one ``foundation_model`` candidate. The promoter
picks them up and admits them like any other agent — same scoring
pipeline, just a different ``entity_kind`` so downstream surfaces
(/models, FM-50) can branch on it.

Daily cadence — model catalogues don't churn faster than that.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import ClassVar

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)


class OpenRouterModelsScout(Scout):
    name: ClassVar[str] = "openrouter_models"
    interval_seconds: ClassVar[int] = 24 * 60 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        try:
            r = await self._http.get("https://openrouter.ai/api/v1/models")
        except Exception as e:  # noqa: BLE001
            log.warning("openrouter fetch failed: %s", e)
            return
        if r.status_code != 200:
            log.warning("openrouter returned %d", r.status_code)
            return
        items = (r.json() or {}).get("data") or []
        for m in items:
            model_id = m.get("id")
            if not model_id:
                continue
            pricing = m.get("pricing") or {}
            top = m.get("top_provider") or {}
            yield Candidate(
                source=DiscoverySource.HUGGINGFACE,  # closest match in current enum
                source_id=f"openrouter:{model_id}",
                raw_payload={
                    # Carry the entity_kind through the payload so the
                    # promoter knows to admit this with kind=foundation_model.
                    "entity_kind": "foundation_model",
                    "openrouter_id": model_id,
                    "name": m.get("name") or model_id,
                    "description": m.get("description"),
                    "context_length": m.get("context_length"),
                    "modality": m.get("architecture", {}).get("modality"),
                    "tokenizer": m.get("architecture", {}).get("tokenizer"),
                    "instruct_type": m.get("architecture", {}).get("instruct_type"),
                    "input_price_per_million": _to_per_million(pricing.get("prompt")),
                    "output_price_per_million": _to_per_million(pricing.get("completion")),
                    "max_completion_tokens": top.get("max_completion_tokens"),
                    "is_moderated": top.get("is_moderated"),
                    "html_url": f"https://openrouter.ai/{model_id}",
                },
            )


def _to_per_million(rate: str | float | None) -> float | None:
    """OpenRouter pricing is per token. We display per million for readability."""
    if rate is None:
        return None
    try:
        return float(rate) * 1_000_000
    except (TypeError, ValueError):
        return None
