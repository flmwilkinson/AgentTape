"""Rebalance narrative generation.

Calls Claude (haiku-4-5) with a prompt-cached system block so the
methodology + tone-of-voice block stays cached across the five weekly
rebalances. Returns ~200 words of human-readable markdown explaining
the biggest changes.

If ``ANTHROPIC_API_KEY`` is unset OR the call fails, falls back to a
deterministic programmatic summary so the rebalances table is never
left without something useful in ``narrative_md``.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from scoring.config import Settings

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the editor for AgentTape, a live index of AI agents.

You write the rebalance reports that get auto-published to /report/[year]/[week].

Tone: brisk, factual, no hype. ~200 words. Markdown allowed but minimal — short paragraphs, no headers needed at this length.

Always cover:
- The biggest *additions* — name the most-notable 1-2 by name and say *why* (one signal-driven sentence each).
- The biggest *removals* — same: name 1-2, say what dropped.
- A one-sentence read on what the diff says about the broader trend (e.g. "browser agents broke into the index this week").

Don't list every change. Don't speculate beyond the diff data. Don't apologize for thin data; if the diff is small, say so plainly."""


async def generate_rebalance_narrative(
    settings: Settings,
    definition: Any,  # IndexDef — typed Any to avoid a circular import
    diff: Any,  # RebalanceDiff
    candidates: list[tuple[UUID, float]],
) -> str:
    """Returns markdown. Best-effort LLM call, falls back to a deterministic summary."""
    if not settings.anthropic_api_key:
        return _fallback(definition, diff, candidates)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        user_text = json.dumps(
            {
                "index": definition.slug,
                "name": definition.name,
                "members_total": len(candidates),
                "additions": diff.additions[:10],
                "removals": diff.removals[:10],
                "weight_changes_count": len(diff.weight_changes),
            },
            default=str,
        )
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
        return msg.content[0].text  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        log.warning("narrative LLM call failed (%s); falling back", e)
        return _fallback(definition, diff, candidates)


def _fallback(definition: Any, diff: Any, candidates: list[tuple[UUID, float]]) -> str:
    """A small deterministic narrative when Claude isn't available."""
    n = len(candidates)
    parts = [f"### {definition.name} rebalance"]
    parts.append(f"{n} constituents this week.")
    if diff.additions:
        sample = ", ".join(a["agent_id"][:8] for a in diff.additions[:3])
        parts.append(f"{len(diff.additions)} new entrants (e.g. {sample}…).")
    if diff.removals:
        sample = ", ".join(r["agent_id"][:8] for r in diff.removals[:3])
        parts.append(f"{len(diff.removals)} dropped (e.g. {sample}…).")
    if not diff.additions and not diff.removals:
        parts.append("Membership unchanged from the prior period.")
    if diff.weight_changes:
        parts.append(f"{len(diff.weight_changes)} weight adjustments under equal-weight v1.")
    return " ".join(parts)
