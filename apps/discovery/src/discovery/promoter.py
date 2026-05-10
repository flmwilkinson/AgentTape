"""Promoter.

Reads pending discovery_candidates, scores each, admits or rejects.

Scoring (max 1.0):
  +0.4  has an LLM dependency (langchain/openai/anthropic/llama-index/crewai/autogen)
  +0.2  README/description matches agent vocabulary
  +0.2  popularity floor: >=50 stars OR >=1000 HF downloads OR present in MCP registry
  +0.1  maintained (commits in last 90 days OR pushed_at recent)
  +0.1  packaged for distribution (npm or PyPI release)

Decision:
  >= settings.auto_admit_threshold  -> admit
  <  settings.auto_reject_threshold -> reject
  in between                         -> stays pending (weekly review)

Admission:
  - generate slug (idempotent on conflict)
  - LLM (best-effort) writes a 2-sentence description and picks tags
  - embedding (best-effort) computed for vibe search
  - emit agent_admitted event into the events table + Redis pub/sub
  - leave a row in agent_tags for each accepted tag
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.config import Settings, get_settings
from discovery.enrichment import compute_embedding, enrich_agent
from discovery.enums import DiscoverySource, DiscoveryVia, EligibilityStatus

log = logging.getLogger(__name__)

LLM_DEP_PATTERNS = re.compile(
    # Frameworks (named in the spec).
    r"\b(langchain|openai|anthropic|llama[-_ ]?index|crew[- ]?ai|autogen|"
    r"litellm|ollama|vllm|google-generativeai|cohere|"
    # "or model API in code" — model names + the umbrella term itself.
    r"gpt[- ]?[345o]?|claude|gemini|mistral|deepseek|llama[- ]?[234]|"
    r"large[- ]?language[- ]?model|llm|llms)\b",
    re.IGNORECASE,
)
AGENT_VOCAB = re.compile(
    r"\b(autonomous|multi[- ]?step|plan(?:s|ning)?|tool[- ]?use|"
    r"browser[- ]?(use|agent)|agent(?:s|ic)?|chain[- ]?of[- ]?thought|"
    r"self[- ]?correct|orchestrat(?:e|ion))\b",
    re.IGNORECASE,
)
SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")
DISCOVERY_VIA_BY_SOURCE: dict[DiscoverySource, DiscoveryVia] = {
    DiscoverySource.GITHUB: DiscoveryVia.GITHUB_SEARCH,
    DiscoverySource.HUGGINGFACE: DiscoveryVia.HF_TRENDING,
    DiscoverySource.MCP_REGISTRY: DiscoveryVia.MCP_REGISTRY,
    DiscoverySource.HACKER_NEWS: DiscoveryVia.HN_SUBMISSION,
    DiscoverySource.NPM: DiscoveryVia.NPM_SEARCH,
    DiscoverySource.PYPI: DiscoveryVia.NPM_SEARCH,  # closest fit in the enum
    DiscoverySource.ARXIV: DiscoveryVia.ARXIV_PAPER,
    DiscoverySource.MANUAL: DiscoveryVia.MANUAL,
}


async def run_promoter(session: AsyncSession, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)

    pending = await session.execute(
        text(
            """
            SELECT id, source, source_id, raw_payload
            FROM discovery_candidates
            WHERE promoted_to_agent_id IS NULL AND rejection_reason IS NULL
            ORDER BY found_at ASC
            LIMIT :cap
            """
        ),
        {"cap": max(settings.max_candidates_per_run * 5, 500)},
    )
    rows = pending.all()

    admitted, rejected, pending_review = 0, 0, 0
    for cand_id, source, source_id, payload in rows:
        p = payload or {}

        # Foundation models from a curated catalogue (openrouter) bypass
        # the agent-shaped scoring rubric — that rubric assumes things
        # like "has an LLM dependency", which is meaningless when the
        # candidate IS an LLM. Admit at a neutral baseline; the scoring
        # service will recompute against model-specific signals.
        if p.get("entity_kind") == "foundation_model":
            await _admit(
                session, redis_client, settings,
                cand_id, source, source_id, p,
                score=settings.auto_admit_threshold,
                reasons={"foundation_model_catalogue": True},
            )
            admitted += 1
            continue

        # Architectural rule: an "agent" must have a deployable
        # artifact — a GitHub repo, a published package, or an HF
        # model id. Without one, it's documentation, marketing copy
        # or a research paper, not a thing a user can run. The arxiv
        # scout used to violate this with paper-as-candidate emits;
        # we patched the scout but pending old candidates still
        # exist in the queue. Defense in depth: reject here too so
        # any future scout that forgets the rule can't pollute the
        # index.
        has_artifact = bool(
            p.get("github_repo")
            or p.get("full_name")
            or p.get("packages")
            or p.get("hf_model_ids")
            or p.get("id")  # HF model/space id
        )
        if not has_artifact:
            await _reject(session, cand_id, 0.0, {"no_deployable_artifact": True})
            rejected += 1
            continue

        score, reasons = score_candidate(p, source)
        if score >= settings.auto_admit_threshold:
            await _admit(
                session,
                redis_client,
                settings,
                cand_id,
                source,
                source_id,
                payload or {},
                score,
                reasons,
            )
            admitted += 1
        elif score < settings.auto_reject_threshold:
            await _reject(session, cand_id, score, reasons)
            rejected += 1
        else:
            # Sticky pending — leave the row alone but record the score so
            # weekly review can sort by it.
            await session.execute(
                text(
                    """
                    UPDATE discovery_candidates
                    SET raw_payload = jsonb_set(
                        COALESCE(raw_payload, CAST('{}' AS jsonb)),
                        '{eligibility}', CAST(:enrich AS jsonb), true
                    )
                    WHERE id = :id
                    """
                ),
                {
                    "id": cand_id,
                    "enrich": json.dumps(
                        {"score": score, "reasons": reasons, "decision": "pending_review"}
                    ),
                },
            )
            pending_review += 1

    await session.commit()
    await redis_client.aclose()
    log.info(
        "promoter: admitted=%d rejected=%d pending_review=%d (of %d candidates)",
        admitted,
        rejected,
        pending_review,
        len(rows),
    )
    return {
        "candidates_seen": len(rows),
        "admitted": admitted,
        "rejected": rejected,
        "pending_review": pending_review,
    }


# --------------------------------------------------------------- scoring


def score_candidate(
    payload: dict[str, Any], source: str
) -> tuple[float, dict[str, Any]]:
    """Return (score, reasons). ``reasons`` is shaped for storage on agents.eligibility_reasons."""
    reasons: dict[str, Any] = {}
    score = 0.0

    blob = _haystack(payload)

    if LLM_DEP_PATTERNS.search(blob):
        score += 0.4
        reasons["llm_dep"] = LLM_DEP_PATTERNS.search(blob).group(0).lower()

    if AGENT_VOCAB.search(blob):
        score += 0.2
        reasons["agent_vocab"] = True

    pop = _popularity_floor(payload, source)
    if pop:
        score += 0.2
        reasons["popularity"] = pop

    if _maintained(payload):
        score += 0.1
        reasons["maintained"] = True

    if _packaged(payload, source):
        score += 0.1
        reasons["packaged"] = True

    return min(score, 1.0), reasons


def _haystack(p: dict[str, Any]) -> str:
    fields = [
        p.get("description"),
        p.get("summary"),
        p.get("name"),
        p.get("full_name"),
        p.get("hn_title"),
        p.get("title"),
        p.get("story_text"),
        " ".join(p.get("topics") or []),
        " ".join(p.get("tags") or []),
        " ".join(p.get("keywords") or []),
        p.get("language"),
    ]
    return " ".join(str(f) for f in fields if f)


def _popularity_floor(p: dict[str, Any], source: str) -> str | None:
    if (p.get("stargazers_count") or 0) >= 50:
        return f"{p['stargazers_count']} stars"
    if (p.get("downloads") or 0) >= 1000:
        return f"{p['downloads']} downloads"
    if (p.get("points") or 0) >= 50:
        return f"{p['points']} HN points"
    if str(source) == DiscoverySource.MCP_REGISTRY.value:
        return "listed in MCP registry"
    return None


def _maintained(p: dict[str, Any]) -> bool:
    for key in ("pushed_at", "lastModified", "updated_at"):
        v = p.get(key)
        if not v:
            continue
        try:
            ts = _parse_dt(v)
        except (ValueError, TypeError):
            continue
        if ts and (datetime.now(UTC) - ts) <= timedelta(days=90):
            return True
    return False


def _packaged(p: dict[str, Any], source: str) -> bool:
    if str(source) in {DiscoverySource.NPM.value, DiscoverySource.PYPI.value}:
        return True
    # Some github candidates declared themselves npm/pypi too.
    return bool(p.get("packages") or p.get("packaged"))


def _parse_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, str):
        # Tolerate trailing Z.
        s = v.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


# ----------------------------------------------------------- admit/reject


async def _admit(
    session: AsyncSession,
    redis_client: Any,
    settings: Settings,
    candidate_id: UUID,
    source: str,
    source_id: str,
    payload: dict[str, Any],
    score: float,
    reasons: dict[str, Any],
) -> None:
    name = _extract_name(payload, source_id)
    slug = _make_slug(name)
    src_enum = DiscoverySource(source) if isinstance(source, str) else source
    via = DISCOVERY_VIA_BY_SOURCE.get(src_enum, DiscoveryVia.MANUAL)

    enrichment = await enrich_agent(settings, payload, name)
    embedding = await compute_embedding(
        settings, f"{name}\n{enrichment.description}"
    )
    # entity_kind is carried through on the payload by scouts that
    # admit non-application stocks (openrouter for foundation_model,
    # eventually mcp registries for mcp_server). Default is application.
    entity_kind = payload.get("entity_kind") or "application"

    # Insert agent. UNIQUE(slug) guarantees idempotency on retries.
    inserted = await session.execute(
        text(
            """
            INSERT INTO agents (
                id, slug, name, description, homepage_url, entity_kind,
                github_repo, hf_org, hf_model_ids, package_names, arxiv_ids,
                discovered_via, eligibility_status, eligibility_score,
                eligibility_reasons, last_admitted_check_at
            ) VALUES (
                gen_random_uuid(), :slug, :name, :desc, :homepage, :entity_kind,
                :github, :hforg, :hfmodels, CAST(:packages AS jsonb), :arxiv,
                CAST(:via AS discovery_via),
                CAST('admitted' AS eligibility_status), :score,
                CAST(:reasons AS jsonb), now()
            )
            ON CONFLICT (slug) DO NOTHING
            RETURNING id
            """
        ),
        {
            "slug": slug,
            "name": name,
            "desc": enrichment.description,
            "homepage": _extract_homepage(payload),
            "entity_kind": entity_kind,
            "github": _extract_github(payload, source_id, src_enum),
            "hforg": _extract_hf_org(payload, src_enum),
            "hfmodels": _extract_hf_models(payload, src_enum),
            "packages": json.dumps(_extract_packages(payload, src_enum)),
            "arxiv": _extract_arxiv(payload, src_enum),
            "via": via.value,
            "score": score,
            "reasons": json.dumps(reasons),
        },
    )
    row = inserted.first()
    if row is None:
        # Slug already taken (admitted via another source). Link the candidate
        # to the existing agent row.
        existing = await session.execute(
            text("SELECT id FROM agents WHERE slug = :slug"), {"slug": slug}
        )
        agent_id = existing.scalar_one()
    else:
        agent_id = row[0]

    if embedding is not None:
        await session.execute(
            text("UPDATE agents SET embedding = :v WHERE id = :id"),
            {"v": str(embedding), "id": agent_id},
        )

    # Tags.
    for kind, values in enrichment.tags.items():
        for value in values:
            await _attach_tag(session, agent_id, kind, value)

    # Mark candidate as promoted.
    await session.execute(
        text(
            "UPDATE discovery_candidates SET promoted_to_agent_id = :aid WHERE id = :cid"
        ),
        {"aid": agent_id, "cid": candidate_id},
    )

    # Event row + Redis publish.
    event_payload = {
        "agent_id": str(agent_id),
        "slug": slug,
        "name": name,
        "score": score,
        "reasons": reasons,
        "via": via.value,
    }
    await session.execute(
        text(
            """
            INSERT INTO events (id, kind, agent_id, payload)
            VALUES (gen_random_uuid(), CAST('agent_admitted' AS event_kind), :aid, CAST(:p AS jsonb))
            """
        ),
        {"aid": agent_id, "p": json.dumps(event_payload)},
    )
    # Publish to events.global (firehose) and events.agent.<slug> (per-agent
    # channel). Both topology keys are documented in apps/realtime — clients
    # subscribe to whichever scope they need without server-side JSON filtering.
    body = json.dumps({"kind": "agent_admitted", **event_payload})
    try:
        await redis_client.publish("events.global", body)
        await redis_client.publish(f"events.agent.{slug}", body)
    except Exception as e:
        log.warning("redis publish failed: %s", e)


async def _reject(
    session: AsyncSession, candidate_id: UUID, score: float, reasons: dict
) -> None:
    await session.execute(
        text(
            """
            UPDATE discovery_candidates
            SET rejection_reason = :reason
            WHERE id = :id
            """
        ),
        {
            "id": candidate_id,
            "reason": json.dumps({"score": score, "reasons": reasons}),
        },
    )


async def _attach_tag(
    session: AsyncSession, agent_id: UUID, kind: str, value: str
) -> None:
    # Idempotent upsert on tags + agent_tags.
    await session.execute(
        text(
            """
            INSERT INTO tags (id, kind, value, display_name)
            VALUES (gen_random_uuid(), CAST(:kind AS tag_kind), :value, :display)
            ON CONFLICT (kind, value) DO NOTHING
            """
        ),
        {"kind": kind, "value": value, "display": value.replace("-", " ").title()},
    )
    res = await session.execute(
        text(
            "SELECT id FROM tags WHERE kind = CAST(:kind AS tag_kind) AND value = :value"
        ),
        {"kind": kind, "value": value},
    )
    tag_id = res.scalar_one()
    await session.execute(
        text(
            """
            INSERT INTO agent_tags (agent_id, tag_id)
            VALUES (:aid, :tid)
            ON CONFLICT DO NOTHING
            """
        ),
        {"aid": agent_id, "tid": tag_id},
    )


# ------------------------------------------------------- payload extractors


def _extract_name(payload: dict[str, Any], source_id: str) -> str:
    # Order matters. Prefer fields the scout set deliberately (name,
    # full_name) over derived ones, then fall back to anything that
    # carries an "owner/repo" form before giving up to source_id.
    # source_id is a last resort because some scouts encode metadata
    # into it (e.g. HN's "<story_id>:<full_name>") which produces
    # ugly slugs like "48068741-owner-repo".
    return (
        payload.get("name")
        or payload.get("full_name")
        or payload.get("github_repo")
        or payload.get("title")
        or source_id
    )


def _extract_homepage(payload: dict[str, Any]) -> str | None:
    return (
        payload.get("homepage")
        or payload.get("html_url")
        or (payload.get("links") or {}).get("homepage")
        or payload.get("home_page")
    )


def _extract_github(
    payload: dict[str, Any], source_id: str, source: DiscoverySource
) -> str | None:
    if source == DiscoverySource.GITHUB:
        return payload.get("full_name") or source_id
    return payload.get("github_repo") or payload.get("full_name")


def _extract_hf_org(payload: dict[str, Any], source: DiscoverySource) -> str | None:
    if source != DiscoverySource.HUGGINGFACE:
        return None
    hf_id = payload.get("id") or ""
    return hf_id.split("/", 1)[0] if "/" in hf_id else None


def _extract_hf_models(
    payload: dict[str, Any], source: DiscoverySource
) -> list[str] | None:
    if source != DiscoverySource.HUGGINGFACE:
        return None
    hf_id = payload.get("id")
    return [hf_id] if hf_id else None


def _extract_packages(
    payload: dict[str, Any], source: DiscoverySource
) -> dict[str, str]:
    out: dict[str, str] = {}
    if source == DiscoverySource.NPM and payload.get("name"):
        out["npm"] = payload["name"]
    if source == DiscoverySource.PYPI and payload.get("name"):
        out["pypi"] = payload["name"]
    return out


def _extract_arxiv(
    payload: dict[str, Any], source: DiscoverySource
) -> list[str] | None:
    if source != DiscoverySource.ARXIV:
        return None
    aid = payload.get("arxiv_id")
    return [aid] if aid else None


def _make_slug(name: str) -> str:
    base = SLUG_NONALNUM.sub("-", name.lower()).strip("-")[:100]
    return base or "agent"
