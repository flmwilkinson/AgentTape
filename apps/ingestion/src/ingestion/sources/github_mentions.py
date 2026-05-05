"""github_mentions_7d — count of distinct GitHub repos referencing
an agent or model name in their content over the past 7 days.

Two flavours of "GitHub stars" matter and they're not the same:
    1. Stars on the project's own repo. Already covered by
       github_stars (a project-level signal).
    2. Mentions in OTHER repos' code or READMEs. Tells you how many
       people are actively *building on* this thing. That's what this
       ingestor measures.

Implementation uses the Code Search API for the count (we only need
total_count, not the hits themselves). Rate-limited at 30 req/min for
authenticated calls and 10 req/min unauthenticated, so we stay on the
MEDIUM tier (one pass per hour).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

CODE_SEARCH = "https://api.github.com/search/code"

# Match a slug-shaped token. We strip provider prefixes from foundation
# model slugs ("openai-gpt-5-3-codex" -> "gpt-5-3-codex") so the search
# doesn't return every repo that says "openai".
_PROVIDER_PREFIXES = (
    "openai-", "anthropic-", "google-", "meta-", "mistral-", "qwen-",
    "deepseek-", "xai-", "nvidia-", "amazon-", "perplexity-", "minimax-",
    "moonshotai-", "z-ai-", "nous-", "arcee-", "sao10k-", "xiaomi-",
)
_NOISE_WORDS = {"agent", "code", "ai", "ml", "llm", "model", "free"}


class GithubMentions7dIngestor(Ingestor):
    name: ClassVar[str] = "github_mentions_7d"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_MENTIONS_7D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        token = self.settings.github_token
        if not token:
            # Code search is gated behind authentication. Without a
            # token we'd burn the anonymous 10 req/min on probably-
            # null results — soft-skip the whole source instead.
            return []

        sem = asyncio.Semaphore(1)  # serialize to respect rate limit
        since = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
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
                count = await _count(self._http, headers, term, since)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.GITHUB_MENTIONS_7D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


def _query_term(a: AgentRow) -> str | None:
    """Pick the most-distinctive token to search code for."""
    name = a.slug or ""
    if not name:
        return None
    # Strip provider prefix on foundation-model slugs so we don't
    # overcount based on the provider name appearing in random code.
    for p in _PROVIDER_PREFIXES:
        if name.startswith(p):
            name = name[len(p):]
            break
    # github_repo "owner/name" — prefer the bare name when present
    # because it's usually more distinctive than the slug.
    if a.github_repo and "/" in a.github_repo:
        bare = a.github_repo.split("/", 1)[1]
        if len(bare) >= 4 and bare.lower() not in _NOISE_WORDS:
            name = bare
    name = name.lower().strip()
    if len(name) < 4:
        return None
    if name in _NOISE_WORDS:
        return None
    return f'"{name}"'


async def _count(http, headers: dict[str, str], term: str, since: str) -> int | None:
    """Return total repo count for the search term in past 7d, or None."""
    # GitHub code search supports a pushed: qualifier on the repo, so
    # we filter to repos updated in the last week. The Search API
    # caps total_count at 1000 even when more matches exist; that's
    # fine — our anchor is 20 mentions, so anything saturating at
    # 1000 just hits the 100 cap on scaled().
    params = {
        "q": f"{term} pushed:>{since}",
        "per_page": 1,  # we only need the count
    }
    try:
        r = await http.get(CODE_SEARCH, headers=headers, params=params)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code == 422:
        # GitHub returns 422 for queries it considers too vague (single
        # common word, etc.). Skip rather than retry.
        return None
    if r.status_code != 200:
        return None
    try:
        return int((r.json() or {}).get("total_count") or 0)
    except (ValueError, TypeError):
        return None
