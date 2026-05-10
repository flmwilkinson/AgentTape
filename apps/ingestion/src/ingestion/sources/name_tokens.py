"""Distinctive search-term derivation for an agent.

The ingestion sources that scan free text — arxiv, news mentions,
benchmark leaderboards — don't all benefit from the same identifier.
``openai-gpt-5`` (the slug we store internally) doesn't appear in arXiv
papers; people write "GPT-5". And ``OpenAI: GPT-5`` (the name the
OpenRouter scout admits) has provider noise we don't want either.

This module centralises that token-derivation logic so every text-
matching source asks the same question the same way:

    "What strings would somebody actually write when they mean this
     agent — exactly this one and not a variant?"

Each FM gets up to four candidate tokens:

  1. The OpenRouter id with provider slash ("openai/gpt-5"). Quoted,
     this is essentially a unique sentinel — code and configs use it.
  2. The clean model name with provider stripped ("GPT-5",
     "Gemini 3 Flash Preview"). The colloquial name humans write.
  3. A no-provider slug ("gpt-5", "gemini-3-flash-preview"). Variant
     of the above, but useful for matching kebab-cased configs.
  4. The full slug as a final fallback ("openai-gpt-5"). Very rare
     to find this verbatim outside our own URLs, but cheap to keep.

Each is wrapped in quotes when handed to a search API that supports
exact-match. Pages that just substring-search should iterate the list
and OR-merge.

Application agents return a smaller token set — usually just the
slug + name — because their identifying tokens (slug) are already
distinctive (no shared "OpenAI:" prefix hiding the real name).
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from ingestion.sources.base import AgentRow

# Provider prefixes we strip off slugs to get the colloquial name.
# Order matters — long prefixes first so "openai-" beats "open-".
_PROVIDER_PREFIXES = (
    "openai-",
    "anthropic-",
    "google-",
    "meta-",
    "mistralai-",
    "mistral-",
    "alibaba-",
    "qwen-",
    "deepseek-",
    "xai-",
    "nvidia-",
    "amazon-",
    "perplexity-",
    "minimax-",
    "moonshotai-",
    "moonshot-",
    "z-ai-",
    "nous-",
    "arcee-",
    "sao10k-",
    "xiaomi-",
    "inclusionai-",
    "tencent-",
    "baidu-",
    "cohere-",
    "01-ai-",
)

# Provider prefixes in display-name form. Many model names start with
# the org colon-separated ("OpenAI: GPT-5", "Anthropic: Claude Opus
# 4.7"); we drop everything before the first ": " when it matches.
_NAME_PROVIDER_PREFIXES = re.compile(
    r"^(?:OpenAI|Anthropic|Google|Meta|MistralAI|Mistral|Alibaba|Qwen|"
    r"DeepSeek|xAI|NVIDIA|Amazon|Perplexity|MiniMax|MoonshotAI|Moonshot|"
    r"Z\.ai|Nous|Arcee|Cohere|01\.AI|Tencent|Baidu)\s*:\s*",
    re.IGNORECASE,
)

# Filter — tokens shorter than this are discarded as too noisy
# ("ai", "ml", "v1" would match everything). Empirically 4 is a good
# floor for FM names — "GPT-5" is 5 chars, "Llama" is 5, "Claude" 6.
_MIN_TOKEN_LEN = 4

# Generic words we'd never want as a search term on their own.
_NOISE = {
    "agent", "code", "ai", "ml", "llm", "model", "free", "fast",
    "pro", "max", "mini", "nano", "thinking", "instruct", "preview",
    "beta", "alpha", "experimental", "free", "chat",
}


def fm_search_tokens(a: AgentRow) -> list[str]:
    """Return distinctive search tokens for a foundation model agent.

    Ordered by specificity (most-specific first). De-duplicated. Empty
    list if the agent has no usable identifiers.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(t: str | None) -> None:
        if not t:
            return
        v = t.strip()
        if not v or len(v) < _MIN_TOKEN_LEN:
            return
        if v.lower() in _NOISE:
            return
        key = v.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(v)

    # 1. OpenRouter id (slash form).
    if a.facts:
        oid = a.facts.get("openrouter_id")
        if isinstance(oid, str):
            _add(oid)

    # 2. Clean display name (drop "OpenAI: " etc).
    if a.name:
        clean_name = _NAME_PROVIDER_PREFIXES.sub("", a.name).strip()
        if clean_name and clean_name != a.name:
            _add(clean_name)
        # Also a "no special chars" version for sites that flatten
        # punctuation ("GPT 5" matches "GPT-5" via word-boundary
        # regex elsewhere).
        flat = re.sub(r"[:\-_/]+", " ", clean_name).strip()
        if flat and flat != clean_name:
            _add(flat)

    # 3. Slug minus provider prefix.
    if a.slug:
        slug_clean = a.slug
        for p in _PROVIDER_PREFIXES:
            if slug_clean.startswith(p):
                slug_clean = slug_clean[len(p):]
                break
        if slug_clean and slug_clean != a.slug:
            _add(slug_clean)

    # 4. Full slug as last resort.
    if a.slug:
        _add(a.slug)

    return out


def app_search_tokens(a: AgentRow) -> list[str]:
    """Tokens for an application — much simpler than FMs because the
    slug is already distinctive (no shared provider prefix to strip).
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(t: str | None) -> None:
        if not t:
            return
        v = t.strip()
        if not v or len(v) < _MIN_TOKEN_LEN:
            return
        if v.lower() in _NOISE:
            return
        key = v.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(v)

    _add(a.slug)
    _add(a.name)
    if a.github_repo:
        last = a.github_repo.split("/")[-1]
        _add(last)
    return out


def search_tokens(a: AgentRow) -> list[str]:
    """Polymorphic helper — picks the right token set for the entity
    kind. Most callers should use this rather than the kind-specific
    helpers above."""
    if a.entity_kind == "foundation_model":
        return fm_search_tokens(a)
    return app_search_tokens(a)


def word_boundary_regex(tokens: Iterable[str]) -> re.Pattern[str]:
    """Build a single regex that matches any of the tokens at a
    word boundary, case-insensitive. Use this for substring-style
    search (benchmarks, news scraping) where naive ``in`` containment
    would over-match — "gpt-5" inside "gpt-5-mini" being the headline
    case to avoid."""
    if not tokens:
        # No tokens = nothing to match. Return a regex that never matches.
        return re.compile(r"(?!.)")
    parts = [re.escape(t) for t in tokens]
    return re.compile(
        r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
