"""github_repos_using_model — GitHub repositories that name a foundation
model in their name, description or README.

Difference from ``github_mentions_7d``: no time window. We measure
the *cumulative* count of repos that have ever built on / documented /
name-checked the model. That's the public signal that a model has
ecosystem traction.

Why this signal exists:
    Closed-weight flagship models (Claude, GPT, Gemini) don't have a
    GitHub repo of their own and don't have a Hugging Face page, so
    the standard signals (stars, HF downloads) come back null. But
    every coding agent on earth depends on one of these models, and
    the repos say so in their READMEs.

Implementation:
    Repository Search (``/search/repositories``) with
    ``in:name,description,readme``. Not Code Search: that counts
    *files*, so one repo vendoring a model list contributed hundreds
    of hits, Gemini 3.1 Flash Lite read 43,392 and every model pegged
    the 100-repo anchor. Repo search read 1,754 for claude-opus-5.5
    and 1 for hy3-preview — a spread the log curve can rank. Repo
    search also allows 30 requests/min authenticated (Code Search:
    10), so all ~550 models fit one paced daily pass; before, the
    unpaced burst hit the secondary limit after ~25 models.

    The search term is the model's own id, not the provider-qualified
    OpenRouter id: ``"anthropic/claude-opus-5.5"`` finds 0 repos because
    nobody writes the slash form in a README. ``:free`` and other
    billing variants are skipped — they are the same model.

Schedule: SLOW tier. The number doesn't move minute-to-minute;
once-a-day is more than enough.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import ClassVar

import httpx

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

REPO_SEARCH = "https://api.github.com/search/repositories"
# Authenticated search allowance is 30 requests / minute.
REQUEST_INTERVAL = 2.1

# Strip provider prefixes from foundation model slugs so the search
# isn't dominated by the provider's name appearing in random repos.
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
            # Search is far more generous authenticated; without a
            # token we'd burn the anonymous 10 req/min on probably-
            # null results — soft-skip the whole source instead.
            return []

        # Foundation models only. Apps already have richer signals
        # (stars, contributors, forks) on their own repos.
        fms = [a for a in agents if a.entity_kind == "foundation_model"]
        if not fms:
            return []

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.settings.user_agent,
        }
        out: list[SignalReading] = []
        for a in fms:
            term = _query_term(a)
            if not term:
                continue
            count = await _count(self._http, headers, term)
            await asyncio.sleep(REQUEST_INTERVAL)
            if count is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.GITHUB_REPOS_USING_MODEL,
                    value=float(count),
                    captured_at=datetime.now(UTC),
                )
            )
        return out


def model_id(a: AgentRow) -> str | None:
    """The model's own id as people write it: the OpenRouter id minus
    its provider (``anthropic/claude-opus-5.5`` -> ``claude-opus-5.5``),
    else the slug minus its provider prefix. None for billing variants
    (``:free``, ``:thinking``)."""
    if a.facts:
        oid = a.facts.get("openrouter_id")
        if isinstance(oid, str) and oid.strip():
            oid = oid.strip().lower()
            if ":" in oid:
                return None
            return oid.split("/", 1)[-1]
    name = (a.slug or "").lower()
    for p in _PROVIDER_PREFIXES:
        if name.startswith(p):
            name = name[len(p):]
            break
    return name or None


def _query_term(a: AgentRow) -> str | None:
    """Search term, or None when the id can't be attributed.

    A single plain word ("pareto", "sonar") matches every README that
    uses the word — "pareto" read 52,323 repos — so those stay Unrated
    here. Known limitation: GitHub's tokeniser makes a base version a
    superset of its point releases ("gpt-5" also counts gpt-5.2 and
    gpt-5-mini READMEs), so families are credited to their base name.
    """
    mid = model_id(a)
    if not mid or len(mid) < 4 or mid in _NOISE_WORDS:
        return None
    if mid.isalpha():
        return None
    return f'"{mid}" in:name,description,readme'


async def _count(
    http: httpx.AsyncClient, headers: dict[str, str], term: str
) -> int | None:
    """Repositories matching the term, or None on any API failure."""
    params: dict[str, str | int] = {"q": term, "per_page": 1}
    for attempt in range(2):
        try:
            r = await http.get(REPO_SEARCH, headers=headers, params=params)
        except Exception:  # noqa: BLE001
            return None
        if r.status_code in (403, 429) and attempt == 0:
            # Secondary rate limit: wait it out once, then give up on
            # this term rather than stall the tier.
            await asyncio.sleep(_retry_delay(r))
            continue
        if r.status_code != 200:
            # 422 = query GitHub deems too vague; skip rather than retry.
            return None
        try:
            return int((r.json() or {}).get("total_count") or 0)
        except (ValueError, TypeError):
            return None
    return None


def _retry_delay(r: httpx.Response) -> float:
    retry_after = r.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 120.0)
    reset = r.headers.get("x-ratelimit-reset")
    if reset and reset.isdigit():
        return min(max(float(reset) - time.time(), 5.0), 120.0)
    return 60.0
