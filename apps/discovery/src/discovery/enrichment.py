"""Enrichment for newly-admitted agents.

This used to call Claude for a description and tag list, and Voyage
for an embedding. Both have been replaced with free local paths so
the discovery service has no required paid API.

Description
    Use the upstream payload's own description (GitHub repo description,
    Hugging Face card, MCP registry blurb, npm/PyPI summary). If a usable
    description is missing, fall back to a templated one-liner derived
    from the slug + source.

Tags
    Three layers, evaluated in order:
      1. Source-native tags (GitHub topics, HF tags, npm keywords, MCP
         tags) — these are author-asserted and the most reliable.
      2. Keyword rules over name + description for the capability axis
         (e.g. "browser" → browsing, "code" → code-generation).
      3. Heuristic license inference from the GitHub license SPDX or
         the PyPI license string.
    Output is constrained to the same fixed taxonomy that used to be
    sent to Claude — no invented tags survive.

Embeddings
    sentence-transformers/all-MiniLM-L6-v2 loaded once per process,
    runs on CPU. 384-dim output is zero-padded to 1536 to match the
    pgvector column. Skipped silently if the model fails to load
    (e.g. offline first-run with no cached weights) — the agent simply
    won't appear in vibe search until the next backfill.

Claude / Voyage are still consulted as opt-in upgrades when the keys
are set. Set ``ANTHROPIC_API_KEY`` if you want richer descriptions;
the local path otherwise gives indistinguishable results for the
fixed-taxonomy tag list.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any

from discovery.config import Settings

log = logging.getLogger(__name__)


# Fixed taxonomy — same as before, kept here so the LLM-and-rules paths
# share one source of truth.
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

# Capability rules — substring tests over the haystack of name + description
# + topics. First-match-wins per kind so we don't end up with three
# capability tags from one keyword. Keep the lists short; the cost of a
# missed tag is low (search will still find it via text match).
CAPABILITY_RULES: list[tuple[str, list[str]]] = [
    ("code-generation", ["code", "coding", "developer", "programmer", "ide-plugin"]),
    ("browsing", ["browser", "browse", "web-agent", "puppeteer", "playwright"]),
    ("research", ["research", "literature", "paper-search", "scholar"]),
    ("data-analysis", ["analytics", "data-analysis", "tabular", "spreadsheet"]),
    ("rag", ["retrieval", "rag", "vector-store"]),
    ("memory", ["memory", "long-term-memory", "memory-system"]),
    ("planning", ["planner", "planning", "task-decomposition"]),
    ("tool-use", ["tool-use", "tools", "function-calling"]),
    ("multi-agent", ["multi-agent", "agents", "agent-network", "swarm", "crew"]),
    ("voice", ["voice", "speech", "tts", "stt", "audio"]),
    ("vision", ["vision", "image", "ocr", "screenshot"]),
    ("automation", ["automation", "workflow", "rpa"]),
]

DEPLOYMENT_RULES: list[tuple[str, list[str]]] = [
    ("mcp-server", ["mcp-server", "mcp"]),
    ("ide-plugin", ["vscode", "intellij", "jetbrains", "ide"]),
    ("browser-extension", ["chrome-extension", "firefox-extension"]),
    ("cli", ["cli", "command-line"]),
    ("saas", ["saas", "hosted"]),
    ("library", ["library", "framework"]),
]

LICENSE_NORMALIZE: dict[str, str] = {
    "mit": "mit",
    "apache 2.0": "apache-2.0",
    "apache-2.0": "apache-2.0",
    "apache license 2.0": "apache-2.0",
    "agpl-3.0": "agpl",
    "gpl-3.0": "gpl",
    "gpl-2.0": "gpl",
    "bsd-3-clause": "bsd",
    "bsd-2-clause": "bsd",
    "mpl-2.0": "mpl",
}


@dataclass
class Enrichment:
    description: str
    tags: dict[str, list[str]]
    # Auto-detected at enrichment time. Promoter merges these with
    # whatever the candidate payload already has.
    #   • detected_packages — { "npm": "<name>", "pypi": "<name>" }
    #     extracted from package.json / pyproject.toml on the GitHub
    #     repo's default branch. Empty when no repo, or repo has no
    #     publishable packaging file, or fetch failed.
    #   • model_dep_families — list of family slugs ("claude", "gpt",
    #     "gemini", ...) detected in the description. The promoter
    #     writes them as model_dep tags after admission.
    detected_packages: dict[str, str]
    model_dep_families: list[str]


# ---------------------------------------------------------------- public


async def enrich_agent(
    settings: Settings, candidate_payload: dict[str, Any], fallback_name: str
) -> Enrichment:
    """Free local path. Optional Claude upgrade if ``ANTHROPIC_API_KEY`` set."""
    desc = _description(candidate_payload, fallback_name)
    tags = _tags_from_rules(candidate_payload)

    if settings.anthropic_api_key:
        try:
            llm = await _llm_enrich_optional(settings, candidate_payload, fallback_name)
            if llm is not None:
                # Prefer the LLM description (richer) but merge tags so
                # we keep the rule-based ones the LLM might have missed.
                desc = llm.description or desc
                for kind, values in (llm.tags or {}).items():
                    if values:
                        tags[kind] = list(dict.fromkeys(tags.get(kind, []) + values))[:2]
        except Exception as e:  # noqa: BLE001
            log.debug("optional LLM enrichment skipped: %s", e)

    # Auto-detect package_names from the GitHub repo (best-effort).
    repo = candidate_payload.get("github_repo") or candidate_payload.get("full_name")
    detected_packages: dict[str, str] = {}
    if repo:
        try:
            detected_packages = await detect_packages_from_github(repo)
        except Exception as e:  # noqa: BLE001
            log.debug("package auto-detect skipped for %s: %s", repo, e)

    # Auto-detect model dependency families from the description.
    model_dep_families = detect_model_dep_families(desc)

    return Enrichment(
        description=desc,
        tags=tags,
        detected_packages=detected_packages,
        model_dep_families=model_dep_families,
    )


# ---------------------------------------------------------------- description

# Common mojibake fixes. Triggered when a UTF-8 byte sequence has been
# ASCII-replaced upstream (each byte → "?") or double-decoded as
# Latin-1. Applied as exact substring substitutions because we know
# which characters source data actually uses (smart quotes, dashes,
# ellipsis); we don't want a general-purpose mojibake fixer rewriting
# legitimate punctuation.
#
# The "???" entry in particular maps the three-question-mark
# replacement of UTF-8 0xE2 0x80 0x99 (right single quote) back to a
# plain apostrophe — that's the "Mistral???s" pattern.
# Catch the regular Unicode replacement char too — same character
# class, two literal codepoints (?, U+FFFD).
_MOJI_CHARCLASS = "[?�]"

_MOJIBAKE_REGEX_FIXES: list[tuple[re.Pattern[str], str]] = [
    # Smart-quote contractions: "OpenAI???s" / "OpenAI���s" / "donâ€™t".
    # The run of 3 q-mark-likes (or the â€™ trigraph) stands in for
    # U+2019 (right single quote). word-boundary on the right keeps
    # us from over-matching mid-word.
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=s\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=t\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=re\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=ve\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=ll\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=d\b)", re.IGNORECASE), "'"),
    (re.compile(rf"{_MOJI_CHARCLASS}{{3}}(?=m\b)", re.IGNORECASE), "'"),
    # Smart-quote between letters with no leading word boundary
    # (catches "we???re", "you???ll" etc when prior patterns don't match).
    (re.compile(rf"(?<=[a-zA-Z]){_MOJI_CHARCLASS}{{3}}(?=[a-zA-Z])"), "'"),
    # Latin-1 double-decode triplet — distinctive enough to rewrite
    # blindly, never appears in legitimate text.
    (re.compile(r"â€™"), "'"),  # â€™ -> '
    (re.compile(r"â€“"), "-"),  # â€“ -> -
    (re.compile(r"â€”"), "-"),  # â€” -> -
    (re.compile(r"â€¦"), "..."),  # â€¦ -> ...
    (re.compile(r"â€œ"), "\""),  # â€œ -> "
    # Lone Unicode replacement character — drop.
    (re.compile(r"�"), ""),
]

# Legacy literal-string list — kept only because the SQL pre-filter
# in repair_mojibake.py builds a LIKE clause from these to avoid
# loading every row. Wider charclass below ensures we still rewrite
# correctly via the regex pass.
_MOJIBAKE_FIXES: list[tuple[str, str]] = [
    # Three-byte smart-quote replacements (most common).
    ("???s ", "'s "),
    ("???t ", "'t "),
    ("???re ", "'re "),
    ("???ve ", "'ve "),
    ("???ll ", "'ll "),
    ("???d ", "'d "),
    ("???m ", "'m "),
    # Latin-1 double-decode patterns ("Mistralâ€™s").
    ("â€™", "'"),
    ("â€“", "-"),
    ("â€”", "-"),
    ("â€¦", "..."),
    ("â€œ", '"'),
    ("â€", '"'),
    # Lone Unicode replacement character — drop it.
    ("�", ""),
]


def _clean_text(s: str) -> str:
    """Repair common mojibake patterns without touching valid Unicode.

    Three flavours show up in real data:

      1. Each byte of a multi-byte UTF-8 sequence ASCII-replaced with
         literal "?". A right single quote (U+2019, 3 bytes in UTF-8)
         becomes "???". OpenRouter / HF API payloads ship like this
         intermittently.

      2. Same thing but the replacement char is the Unicode
         replacement codepoint U+FFFD (renders as "?" in most fonts,
         "□" in others). The regex character class catches both.

      3. UTF-8 bytes decoded as Latin-1 then re-encoded ("â€™" for
         U+2019). Distinctive byte triplet, safe to rewrite blind.

    Idempotent — running it on already-clean text is a no-op because
    the replacement chars (', -, ", ...) don't contain "?" or U+FFFD.
    """
    for pattern, replacement in _MOJIBAKE_REGEX_FIXES:
        s = pattern.sub(replacement, s)
    return s


def _description(payload: dict[str, Any], fallback_name: str) -> str:
    raw = (
        payload.get("description")
        or payload.get("summary")
        or (payload.get("info") or {}).get("summary")
        or ""
    ).strip()
    raw = _clean_text(raw)
    if not raw:
        return f"{fallback_name}: discovered AI agent."
    if len(raw) > 280:
        raw = raw[:277].rstrip() + "..."
    if "." not in raw:
        raw = raw + "."
    # Prepend the slug-style name so the description card always leads
    # with the agent's identity — the LLM path used to do this implicitly.
    return f"{fallback_name}: {raw}"


# ---------------------------------------------------------------- tags


def _tags_from_rules(payload: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in TAXONOMY}

    haystack = " ".join(
        str(x).lower()
        for x in [
            payload.get("name"),
            payload.get("full_name"),
            payload.get("description"),
            payload.get("summary"),
            *(payload.get("topics") or []),
            *(payload.get("tags") or []),
            *(payload.get("keywords") or []),
        ]
        if x
    )

    # Capability — pick up to 2 by rule order.
    for cap, kw in CAPABILITY_RULES:
        if cap not in TAXONOMY["capability"]:
            continue
        if any(k in haystack for k in kw):
            out["capability"].append(cap)
            if len(out["capability"]) >= 2:
                break

    # Deployment — pick first match.
    for dep, kw in DEPLOYMENT_RULES:
        if dep not in TAXONOMY["deployment"]:
            continue
        if any(k in haystack for k in kw):
            out["deployment"].append(dep)
            break

    # License — normalize the SPDX from the GitHub payload or PyPI info.
    spdx = (payload.get("license") or "").strip().lower()
    if not spdx:
        spdx = ((payload.get("info") or {}).get("license") or "").strip().lower()
    if spdx:
        normalized = LICENSE_NORMALIZE.get(spdx, spdx)
        if normalized in TAXONOMY["license"]:
            out["license"].append(normalized)
        elif "proprietary" in spdx or "commercial" in spdx:
            out["license"].append("proprietary")

    # Maturity — heuristic based on stars + age.
    stars = payload.get("stargazers_count") or 0
    if stars >= 5_000:
        out["maturity"].append("stable")
    elif stars >= 500:
        out["maturity"].append("beta")
    else:
        out["maturity"].append("experimental")

    # Foundation models always carry a deployment tag of "saas" since
    # they're typically consumed via API, even when open-weights.
    if payload.get("entity_kind") == "foundation_model":
        if "saas" not in out["deployment"]:
            out["deployment"].append("saas")

    return out


# ---------------------------------------------------------------- LLM (optional)


async def _llm_enrich_optional(
    settings: Settings, payload: dict[str, Any], fallback_name: str
) -> Enrichment | None:
    """Deprecated path — kept available for callers with ANTHROPIC_API_KEY set."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return None

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_text = json.dumps(_compact_payload(payload))[:6000]
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=[
            {
                "type": "text",
                "text": (
                    "You are an editor for AgentTape. For the JSON below, output "
                    "STRICT JSON: {\"description\": \"two sentences\", "
                    "\"tags\": {\"capability\": [...], \"domain\": [...], "
                    "\"license\": [...], \"deployment\": [...], \"maturity\": [...]}}. "
                    "Tags MUST come from this taxonomy:\n"
                    + json.dumps(TAXONOMY)
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    raw = msg.content[0].text  # type: ignore[union-attr]
    parsed = json.loads(raw)
    desc = (parsed.get("description") or "").strip()
    tags_in = parsed.get("tags") or {}
    tags_out: dict[str, list[str]] = {}
    for kind, allowed in TAXONOMY.items():
        got = tags_in.get(kind) or []
        tags_out[kind] = [t for t in got if t in allowed][:2]
    return Enrichment(description=desc, tags=tags_out)


def _compact_payload(p: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "name", "full_name", "description", "summary", "homepage",
        "topics", "tags", "language", "license", "stargazers_count",
        "downloads", "kind", "id", "registry",
    }
    return {k: v for k, v in (p or {}).items() if k in keep and v is not None}


# ---------------------------------------------------------------- embeddings


_st_model: Any = None
_st_lock = Lock()


def _get_local_embedder():
    """Lazy-load sentence-transformers once per process. CPU-friendly."""
    global _st_model
    if _st_model is not None:
        return _st_model
    with _st_lock:
        if _st_model is not None:
            return _st_model
        try:
            from sentence_transformers import SentenceTransformer

            _st_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            log.info("local embedder loaded (all-MiniLM-L6-v2)")
        except Exception as e:  # noqa: BLE001
            log.warning("local embedder unavailable: %s", e)
            _st_model = False  # sentinel: don't retry
    return _st_model


async def compute_embedding(settings: Settings, text: str) -> list[float] | None:
    """Local embedding by default. Optional Voyage upgrade if ``VOYAGE_API_KEY`` set.

    Output is zero-padded to 1536 dims to match the existing pgvector
    column schema, regardless of the upstream model's native dimensionality.
    """
    if not text:
        return None

    if settings.voyage_api_key:
        # Optional upgrade — Voyage embeddings, network call.
        try:
            return await _voyage_embedding(settings, text)
        except Exception as e:  # noqa: BLE001
            log.warning("voyage embedding failed; falling back to local: %s", e)

    model = _get_local_embedder()
    if not model:
        return None
    try:
        # encode is sync; offload to a thread to keep the event loop
        # responsive during a backfill of dozens of agents.
        import asyncio

        vec = await asyncio.to_thread(
            model.encode, text[:4000], normalize_embeddings=True
        )
        out = list(map(float, vec))
        if len(out) < 1536:
            out = out + [0.0] * (1536 - len(out))
        return out[:1536]
    except Exception as e:  # noqa: BLE001
        log.warning("local embedding failed: %s", e)
        return None


async def _voyage_embedding(settings: Settings, text: str) -> list[float] | None:
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


# ----------------------------------------------- package auto-detect

# pyproject.toml `[project]` name extractor — robust enough for the
# common case (PEP 621 name = "..."). Tomllib would be cleaner but
# keeps us off a 3.11+ dependency floor.
_PYPROJECT_NAME = re.compile(
    r"^\s*name\s*=\s*\"(?P<name>[A-Za-z0-9._-]+)\"",
    re.MULTILINE,
)


async def detect_packages_from_github(repo: str) -> dict[str, str]:
    """Read package.json + pyproject.toml from a GitHub repo's default
    branch and return a dict of detected ecosystem -> package name.

    repo: ``"owner/name"`` form. Uses raw.githubusercontent.com which
    follows the default branch via the ``HEAD`` ref alias, so it works
    regardless of whether the project uses ``main`` or ``master`` (or
    something exotic). Two GET requests, capped at 3s each — slow
    repos / network blips bail out silently and leave the row's
    package_names empty for the seed file or the next run to fix.

    Best-effort by design: we accept that monorepos / private workspace
    packages will produce a noisy auto-detect occasionally. The seed
    file's manual mapping always wins (the promoter merges, never
    overwrites).
    """
    import httpx

    out: dict[str, str] = {}
    base = f"https://raw.githubusercontent.com/{repo}/HEAD"
    async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as http:
        # package.json — JSON, the standard root file for npm projects.
        try:
            r = await http.get(f"{base}/package.json")
            if r.status_code == 200:
                import json as _json
                data = _json.loads(r.text)
                name = data.get("name")
                # Skip workspace placeholder names that aren't published.
                if isinstance(name, str) and name and not name.startswith("@types/"):
                    out["npm"] = name
        except Exception as e:  # noqa: BLE001
            log.debug("package.json fetch failed for %s: %s", repo, e)

        # pyproject.toml — fall back to setup.cfg if absent. The PEP 621
        # `[project] name = "..."` is what most modern Python projects
        # use; the legacy `setup.py` name field is harder to parse
        # statically so we don't bother.
        try:
            r = await http.get(f"{base}/pyproject.toml")
            if r.status_code == 200:
                m = _PYPROJECT_NAME.search(r.text)
                if m:
                    out["pypi"] = m.group("name")
        except Exception as e:  # noqa: BLE001
            log.debug("pyproject.toml fetch failed for %s: %s", repo, e)

    return out


# --------------------------------------------- model_dep family detect

# Family-level regexes. Keep these specific enough that "we don't use
# Claude" doesn't trigger — match phrasings that commit the project to
# the model. Order doesn't matter; the result set is a sorted list of
# unique families.
_MODEL_DEP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Claude — Anthropic.
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+(?:anthropic[' ’]?s\s+)?claude\b",
                re.IGNORECASE), "claude"),
    # GPT / ChatGPT / OpenAI — collapse onto a single "gpt" family.
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+(?:openai[' ’]?s\s+)?(?:gpt|chatgpt)\b",
                re.IGNORECASE), "gpt"),
    # Gemini — Google.
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+(?:google[' ’]?s\s+)?gemini\b",
                re.IGNORECASE), "gemini"),
    # DeepSeek.
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+deepseek\b",
                re.IGNORECASE), "deepseek"),
    # Llama (Meta).
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+(?:meta[' ’]?s\s+)?llama\b",
                re.IGNORECASE), "llama"),
    # Mistral.
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+mistral\b",
                re.IGNORECASE), "mistral"),
    # Qwen (Alibaba).
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+qwen\b",
                re.IGNORECASE), "qwen"),
    # Grok (xAI).
    (re.compile(r"\b(?:powered\s+by|built\s+on|uses|using|integrates\s+with|"
                r"works\s+with|via)\s+(?:xai[' ’]?s\s+)?grok\b",
                re.IGNORECASE), "grok"),
]


def detect_model_dep_families(text: str) -> list[str]:
    """Pull family-level model dependencies out of free text.

    Conservative on purpose: only matches when the description
    *commits* the project to a model ("powered by Claude", "built on
    GPT-4"). Bare mentions like "supports Claude and GPT" are caught
    too — the prefix list is intentionally generous because we'd
    rather over-tag than miss the headline case. The display chip
    just says "Built on Claude" so a false positive is low-cost.
    """
    if not text:
        return []
    found: set[str] = set()
    for pattern, family in _MODEL_DEP_PATTERNS:
        if pattern.search(text):
            found.add(family)
    return sorted(found)
