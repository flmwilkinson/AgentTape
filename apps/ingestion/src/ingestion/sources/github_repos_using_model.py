"""github_repos_using_model — total GitHub repos referencing a
foundation model's name in their code or README.

Difference from ``github_mentions_7d``: no time window. We measure
the *cumulative* count of repos that have ever depended on / called /
named-checked the model. That's the public signal that a model has
ecosystem traction, which is what FM Community is about.

Why this signal exists:
    Closed-weight flagship models (Claude, GPT, Gemini) don't have a
    GitHub repo of their own and don't have a Hugging Face page, so
    the standard FM Community signals (HF likes, contributors) come
    back null and the pillar is Unrated. But every coding agent on
    earth depends on one of these models. Counting how many distinct
    repos call the model gives Community a real number to anchor on.

Implementation:
    Same Code Search endpoint as github_mentions_7d, with the
    ``pushed:>`` qualifier removed. We only care about ``total_count``
    so we ask for a single result page. Limited to foundation models
    — application agents have github_contributors / github_forks for
    Community already, and broadening to apps would noisily double
    count repos that include those agents as dependencies.

Schedule: SLOW tier. The number doesn't move minute-to-minute;
once-a-day is more than enough.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

CODE_SEARCH = "https://api.github.com/search/code"

# Strip provider prefixes from foundation model slugs so the search
# isn't dominated by the provider's name appearing in random code.
_PROVIDER_PREFIXES = (
    "openai-", "anthropic-", "google-", "meta-", "mistral-", "qwen-",
    "deepseek-", "xai-", "nvidia-", "amazon-", "perplexity-", "minimax-",
    "moonshotai-", "z-ai-", "nous-", "arcee-", "sao10k-", "xiaomi-",
    "inclusionai-", "tencent-", "baidu-",
)
_NOISE_WORDS = {"agent", "code", "ai", "ml", "llm", "model", "free", "fast", "pro", "max"}


class GithubReposUsingModelIngestor(Ingestor):
    name: ClassVar[str] = "github_repos_using_model"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_REPOS_USING_MODEL
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.github_token
        if not token:
            # Code search requires authentication. Without a token
            # we'd burn the anonymous 10 req/min on probably-null
            # results — soft-skip the whole source instead.
            return []

        # Foundation models only. Apps already have richer Community
        # signals (contributors, forks); searching the entire app
        # corpus this way would multiply the GitHub Code Search
        # quota cost by ~5x for very little additional information.
        fms = [a for a in agents if a.entity_kind == "foundation_model"]
        if not fms:
            return []

        sem = asyncio.Semaphore(1)  # serialize to respect rate limit
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.settings.user_agent,
        }

        async def one(a: AgentRow) -> SignalReading | None:
            term = _query_term(a)
            if not term:
                return None
            async with sem:
                count = await _count(self._http, headers, term)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.GITHUB_REPOS_USING_MODEL,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in fms))
        return [r for r in results if r is not None]


def _query_term(a: AgentRow) -> str | None:
    """Pick the most-distinctive token to search code for.

    For OpenRouter-sourced models, the slug usually has the form
    ``provider-model-version`` (e.g. ``anthropic-claude-opus-4-7``).
    We strip the provider prefix so we don't get a hit from every
    file that imports ``import anthropic`` — we want files that
    actually reference *this* model id specifically.
    """
    name = a.slug or ""
    if not name:
        return None
    for p in _PROVIDER_PREFIXES:
        if name.startswith(p):
            name = name[len(p):]
            break
    name = name.lower().strip()
    if len(name) < 4 or name in _NOISE_WORDS:
        return None
    # Quote the term so multi-word slugs like "claude-opus-4-7" match
    # the exact substring, not the union of words.
    return f'"{name}"'


async def _count(http, headers: dict[str, str], term: str) -> int | None:
    """Return total repo count for the search term across all of
    GitHub, or None on any API failure.

    GitHub Code Search caps total_count at 1000 even when more matches
    exist; that's fine — our anchor is 100, so anything that would
    saturate at 1000 also pegs the 100 ceiling on scaled().
    """
    params = {"q": term, "per_page": 1}
    try:
        r = await http.get(CODE_SEARCH, headers=headers, params=params)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code == 422:
        # GitHub rejects queries it deems too vague (single common
        # word, etc.). Skip rather than retry.
        return None
    if r.status_code != 200:
        return None
    try:
        return int((r.json() or {}).get("total_count") or 0)
    except (ValueError, TypeError):
        return None
