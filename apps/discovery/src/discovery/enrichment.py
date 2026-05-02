"""LLM enrichment for admitted agents.

Uses Claude (claude-haiku-4-5 by default — cheapest, fast enough for
batch enrichment of 100s of new agents per day) to:

- Write a concrete 2-sentence description.
- Pick capability/domain/license/deployment tags from a fixed taxonomy.

Prompt caching (5-min TTL) is enabled on the system prompt so the
taxonomy + instructions don't get re-billed for every agent.

Both calls degrade gracefully: if ANTHROPIC_API_KEY is missing or the
call fails we return a rule-based fallback so the pipeline still admits.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from discovery.config import Settings

log = logging.getLogger(__name__)

# Fixed taxonomy. Tags MUST come from this set — Claude's output is
# validated against it and unknown values are dropped.
TAXONOMY: dict[str, list[str]] = {
    "capability": [
        "code-generation",
        "code-review",
        "research",
        "browsing",
        "data-analysis",
        "automation",
        "planning",
        "tool-use",
        "rag",
        "memory",
        "multi-agent",
        "voice",
        "vision",
    ],
    "domain": [
        "general",
        "developer-tools",
        "customer-support",
        "sales",
        "finance",
        "legal",
        "healthcare",
        "education",
        "marketing",
        "ops",
        "security",
        "research",
    ],
    "license": [
        "mit",
        "apache-2.0",
        "agpl",
        "gpl",
        "bsd",
        "mpl",
        "proprietary",
        "unknown",
    ],
    "deployment": [
        "self-hosted",
        "cli",
        "library",
        "saas",
        "browser-extension",
        "ide-plugin",
        "mcp-server",
    ],
    "maturity": ["experimental", "beta", "stable"],
}

SYSTEM_PROMPT = """You are an editor for AgentTape, a live index of AI agents.

Your job: given a discovered project, write a crisp 2-sentence description and assign tags from a fixed taxonomy.

Rules:
- The description is exactly two sentences. First sentence: what it is (one noun phrase + a verb phrase). Second sentence: what makes it specific (a differentiator or capability).
- Tags MUST be drawn ONLY from the taxonomy below. Pick at most 2 per kind. If you don't know, return an empty list for that kind — never invent.
- Output STRICT JSON with this exact shape:
  {
    "description": "Two sentences.",
    "tags": {
      "capability": [...],
      "domain": [...],
      "license": [...],
      "deployment": [...],
      "maturity": [...]
    }
  }
- No prose, no markdown, no code fences. JSON only.

Taxonomy:
""" + json.dumps(TAXONOMY, indent=2)


@dataclass
class Enrichment:
    description: str
    tags: dict[str, list[str]]


async def enrich_agent(
    settings: Settings, candidate_payload: dict[str, Any], fallback_name: str
) -> Enrichment:
    if not settings.anthropic_api_key:
        return _fallback(candidate_payload, fallback_name)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        user_text = json.dumps(_compact_payload(candidate_payload))[:6000]

        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_text}],
        )
        raw = msg.content[0].text  # type: ignore[union-attr]
        parsed = json.loads(raw)
        return _validate(parsed, candidate_payload, fallback_name)
    except Exception as e:  # broad on purpose: enrichment is best-effort
        log.warning("LLM enrichment failed (%s); falling back to rules", e)
        return _fallback(candidate_payload, fallback_name)


def _compact_payload(p: dict[str, Any]) -> dict[str, Any]:
    """Shrink the raw payload before sending to the model."""
    keep = {
        "name",
        "full_name",
        "description",
        "summary",
        "homepage",
        "topics",
        "tags",
        "language",
        "license",
        "stargazers_count",
        "downloads",
        "kind",
        "id",
        "registry",
    }
    return {k: v for k, v in (p or {}).items() if k in keep and v is not None}


def _validate(
    parsed: dict[str, Any], payload: dict[str, Any], fallback_name: str
) -> Enrichment:
    description = (parsed.get("description") or "").strip()
    if not description:
        description = _fallback_desc(payload, fallback_name)
    tags_in = parsed.get("tags") or {}
    tags_out: dict[str, list[str]] = {}
    for kind, allowed in TAXONOMY.items():
        got = tags_in.get(kind) or []
        tags_out[kind] = [t for t in got if t in allowed][:2]
    return Enrichment(description=description, tags=tags_out)


def _fallback(payload: dict[str, Any], fallback_name: str) -> Enrichment:
    return Enrichment(
        description=_fallback_desc(payload, fallback_name),
        tags={k: [] for k in TAXONOMY},
    )


def _fallback_desc(payload: dict[str, Any], fallback_name: str) -> str:
    desc = (
        payload.get("description")
        or payload.get("summary")
        or "An AI agent project."
    )
    desc = desc.strip()
    if len(desc) > 280:
        desc = desc[:277] + "..."
    if "." not in desc:
        desc = desc + "."
    return f"{fallback_name}: {desc}"


# --- embeddings (optional) ---------------------------------------------


async def compute_embedding(settings: Settings, text: str) -> list[float] | None:
    """Voyage-3 produces 1024-dim; we pad to 1536 to fit the schema column.

    Returns None when no key is configured. Padding is a stopgap until we
    decide on a permanent provider — the column was sized for OpenAI's
    text-embedding-3-small (1536). We don't search on these yet, so the
    padding is harmless.
    """
    if not settings.voyage_api_key or not text:
        return None
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
                json={"input": [text[:4000]], "model": "voyage-3"},
            )
            r.raise_for_status()
            vec = r.json()["data"][0]["embedding"]
            if len(vec) < 1536:
                vec = vec + [0.0] * (1536 - len(vec))
            return vec[:1536]
    except Exception as e:
        log.warning("embedding call failed: %s", e)
        return None
