"""Read-only SQL helpers shared across routers.

All queries here are async, use ``text()`` with named binds, and return
plain dicts — Pydantic models live in ``schemas.py``.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Columns we always select for an agent summary; kept in one place so the
# field list and the dict keys stay in sync.
AGENT_COLS = (
    "a.id, a.slug, a.name, a.description, a.discovered_via, a.discovered_at, "
    "a.homepage_url, a.github_repo, a.entity_kind"
)
SCORE_COLS = (
    "cs.agent_score, cs.adoption, cs.quality, cs.momentum, cs.community, "
    "cs.manipulation_resistance, cs.computed_at"
)
# 24h-old score lookup. Computed in a LATERAL subquery — for each agent
# we grab the most recent score row strictly older than now()-24h. NULL
# when an agent has fewer than 24h of history (the UI shows "—").
SCORE_24H_LATERAL = (
    "LEFT JOIN LATERAL ("
    "  SELECT s.agent_score AS score_24h_ago FROM scores s "
    "  WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours' "
    "  ORDER BY s.computed_at DESC LIMIT 1"
    ") s24 ON true"
)
SCORE_24H_COL = "s24.score_24h_ago"

# Rank lookup. Self-contained subquery so it can plug into any SELECT
# without a CTE prefix. Joins each agent to:
#   rank_now      — global rank within its entity_kind by current
#                   AgentScore DESC (1 = top of the kind)
#   rank_24h_ago  — same, but ordered by score_24h_ago. NULL when an
#                   agent has no 24h history yet.
# The window function runs once per request — fine at our scale.
RANKS_JOIN = """LEFT JOIN (
    SELECT
        ar_a.id,
        ROW_NUMBER() OVER (
            PARTITION BY ar_a.entity_kind
            ORDER BY ar_cs.agent_score DESC NULLS LAST, ar_a.slug ASC
        ) AS rank_now,
        CASE WHEN ar_s24h.score_24h_ago IS NULL THEN NULL
             ELSE ROW_NUMBER() OVER (
                 PARTITION BY ar_a.entity_kind
                 ORDER BY ar_s24h.score_24h_ago DESC NULLS LAST, ar_a.slug ASC
             )
        END AS rank_24h_ago
    FROM agents ar_a
    LEFT JOIN current_scores ar_cs ON ar_cs.agent_id = ar_a.id
    LEFT JOIN LATERAL (
        SELECT s.agent_score AS score_24h_ago FROM scores s
        WHERE s.agent_id = ar_a.id AND s.computed_at <= now() - interval '24 hours'
        ORDER BY s.computed_at DESC LIMIT 1
    ) ar_s24h ON true
    WHERE ar_a.eligibility_status = 'admitted'
) ar ON ar.id = a.id"""
RANKS_COLS = "ar.rank_now, ar.rank_24h_ago"


def _row_to_agent_summary(row: Any) -> dict[str, Any]:
    """Map a SELECT AGENT_COLS, SCORE_COLS, SCORE_24H_COL row to the AgentSummary shape."""
    score_now = float(row.agent_score) if row.agent_score is not None else None
    score_24h = (
        float(row.score_24h_ago)
        if getattr(row, "score_24h_ago", None) is not None
        else None
    )
    delta_24h = (
        score_now - score_24h
        if score_now is not None and score_24h is not None
        else None
    )
    rank_now = (
        int(row.rank_now) if getattr(row, "rank_now", None) is not None else None
    )
    rank_24h_ago = (
        int(row.rank_24h_ago)
        if getattr(row, "rank_24h_ago", None) is not None
        else None
    )
    raw_payload = getattr(row, "raw_payload", None)
    facts = _extract_facts(
        getattr(row, "entity_kind", "application"), raw_payload
    )
    # Tags arrive as an array of "kind:value" strings from the SQL
    # array_agg. Empty array if the agent has no tags.
    tag_pairs = getattr(row, "tag_pairs", None) or []
    tags_summary: list[dict[str, str]] = []
    for pair in tag_pairs:
        if not pair or ":" not in pair:
            continue
        kind, value = pair.split(":", 1)
        tags_summary.append({"kind": kind, "value": value})
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "description": row.description,
        "discovered_via": row.discovered_via,
        "discovered_at": row.discovered_at,
        "homepage_url": row.homepage_url,
        "github_repo": row.github_repo,
        "entity_kind": getattr(row, "entity_kind", "application"),
        "facts": facts,
        "tags": tags_summary,
        "score": {
            "agent_score": score_now,
            "adoption": float(row.adoption) if row.adoption is not None else None,
            "quality": float(row.quality) if row.quality is not None else None,
            "momentum": float(row.momentum) if row.momentum is not None else None,
            "community": float(row.community) if row.community is not None else None,
            "manipulation_resistance": (
                float(row.manipulation_resistance)
                if row.manipulation_resistance is not None
                else None
            ),
            "computed_at": row.computed_at,
            # 24-hour score delta. A 0 means "computed but unchanged",
            # NULL means "no history old enough" — the UI must distinguish.
            "score_24h_ago": score_24h,
            "delta_24h": delta_24h,
            # Rank within entity_kind (global, not page-local).
            "rank_now": rank_now,
            "rank_24h_ago": rank_24h_ago,
            # Frontend usually wants the delta directly. Positive = climbed.
            "rank_delta_24h": (
                rank_24h_ago - rank_now
                if rank_now is not None and rank_24h_ago is not None
                else None
            ),
        },
    }


# ----------------------------------------------------------- agents list


async def list_agents(
    session: AsyncSession,
    *,
    q: str | None,
    tag_kind: str | None,
    tag_value: str | None,
    sort: str,
    limit: int,
    offset: int,
    entity_kind: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where = ["a.eligibility_status = 'admitted'"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    join = ""

    if q:
        where.append(
            "(a.slug ILIKE :q OR a.name ILIKE :q OR a.description ILIKE :q)"
        )
        params["q"] = f"%{q}%"

    if entity_kind:
        where.append("a.entity_kind = :entity_kind")
        params["entity_kind"] = entity_kind

    if tag_kind and tag_value:
        join += (
            " JOIN agent_tags at ON at.agent_id = a.id"
            " JOIN tags t ON t.id = at.tag_id"
            " AND t.kind = CAST(:tag_kind AS tag_kind) AND t.value = :tag_value"
        )
        params["tag_kind"] = tag_kind
        params["tag_value"] = tag_value

    sort_clause = {
        "score": "cs.agent_score DESC NULLS LAST",
        "discovered": "a.discovered_at DESC",
        "name": "a.name ASC",
    }.get(sort, "cs.agent_score DESC NULLS LAST")

    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS},
               dc.raw_payload,
               (
                   SELECT array_agg(t.kind::text || ':' || t.value)
                   FROM agent_tags at_inner
                   JOIN tags t ON t.id = at_inner.tag_id
                   WHERE at_inner.agent_id = a.id
               ) AS tag_pairs
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        LEFT JOIN LATERAL (
            SELECT raw_payload FROM discovery_candidates
            WHERE promoted_to_agent_id = a.id
            ORDER BY found_at DESC LIMIT 1
        ) dc ON true
        {RANKS_JOIN}
        {join}
        WHERE {' AND '.join(where)}
        ORDER BY {sort_clause}
        LIMIT :limit OFFSET :offset
    """
    rows = (await session.execute(text(sql), params)).all()

    total_sql = f"""
        SELECT count(*) FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        {join}
        WHERE {' AND '.join(where)}
    """
    total = (await session.execute(text(total_sql), params)).scalar_one()

    return [_row_to_agent_summary(r) for r in rows], int(total)


# -------------------------------------------------------------- agent detail


async def get_agent_by_slug(
    session: AsyncSession, slug: str
) -> dict[str, Any] | None:
    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS},
               a.hf_org, a.hf_model_ids, a.package_names, a.arxiv_ids,
               a.eligibility_status, a.eligibility_score,
               a.eligibility_reasons, a.manipulation_flags,
               dc.raw_payload
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        LEFT JOIN LATERAL (
            SELECT raw_payload FROM discovery_candidates
            WHERE promoted_to_agent_id = a.id
            ORDER BY found_at DESC LIMIT 1
        ) dc ON true
        {RANKS_JOIN}
        WHERE a.slug = :slug
    """
    row = (await session.execute(text(sql), {"slug": slug})).first()
    if row is None:
        return None
    summary = _row_to_agent_summary(row)
    summary.update(
        hf_org=row.hf_org,
        hf_model_ids=row.hf_model_ids,
        package_names=row.package_names,
        arxiv_ids=row.arxiv_ids,
        eligibility_status=row.eligibility_status,
        eligibility_score=(
            float(row.eligibility_score) if row.eligibility_score is not None else None
        ),
        eligibility_reasons=row.eligibility_reasons,
        manipulation_flags=row.manipulation_flags,
        tags=await _agent_tags(session, row.id),
        facts=_extract_facts(summary.get("entity_kind"), row.raw_payload),
    )
    return summary


def _extract_facts(
    entity_kind: str | None, raw_payload: dict[str, Any] | None
) -> dict[str, Any]:
    """Surface the source-of-truth metadata that wasn't already promoted
    onto the agents row. Used by the agent page facts panel — the
    signals time-series isn't the right shape for a foundation model.
    """
    if not raw_payload:
        return {}
    if entity_kind == "foundation_model":
        keys = (
            "openrouter_id",
            "context_length",
            "max_completion_tokens",
            "modality",
            "tokenizer",
            "instruct_type",
            "input_price_per_million",
            "output_price_per_million",
            "is_moderated",
            "html_url",
        )
        out = {k: raw_payload.get(k) for k in keys if raw_payload.get(k) is not None}
        return out
    return {}


async def compute_retention_badge(
    session: AsyncSession, agent_id: Any
) -> dict[str, Any] | None:
    """Month-2 retention proxy.

    Compare the agent's *current* score against its score 30 days
    after it was admitted. Ratio > 1 means it kept growing past launch
    hype; ratio < 0.5 means it's already decaying. Returns None if the
    agent is < 60 days old (not enough room for a "month-2" window) or
    we don't have a score from the comparison point.

    The return type is the dict shape RetentionBadge expects so the
    route can drop it straight onto the response.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT
                    a.discovered_at,
                    cs.agent_score AS score_now,
                    (
                        SELECT s.agent_score FROM scores s
                        WHERE s.agent_id = a.id
                          AND s.computed_at >= a.discovered_at + interval '30 days'
                        ORDER BY s.computed_at ASC
                        LIMIT 1
                    ) AS score_at_30d
                FROM agents a
                LEFT JOIN current_scores cs ON cs.agent_id = a.id
                WHERE a.id = :aid
                """
            ),
            {"aid": agent_id},
        )
    ).first()
    if row is None:
        return None

    discovered_at = row.discovered_at
    if discovered_at is None:
        return None
    days_since = (datetime.now(UTC) - discovered_at).days
    if days_since < 60:
        return None
    if row.score_now is None or row.score_at_30d is None:
        return None
    score_now = float(row.score_now)
    score_at_30d = float(row.score_at_30d)
    if score_at_30d <= 0:
        return None

    ratio = score_now / score_at_30d
    if ratio >= 1.10:
        status = "growing"
    elif ratio >= 0.90:
        status = "holding"
    elif ratio >= 0.50:
        status = "fading"
    else:
        status = "decaying"
    return {
        "ratio": ratio,
        "status": status,
        "score_now": score_now,
        "score_at_30d": score_at_30d,
        "days_since_admission": days_since,
    }


async def compute_openrouter_rank(
    session: AsyncSession, agent_id: Any
) -> dict[str, Any] | None:
    """Position in the OpenRouter token-volume cohort for foundation models.

    Pulls the most-recent ``openrouter_token_volume_30d`` reading per
    agent and returns this agent's 1-indexed rank within the cohort.
    None when this agent has no recent reading or fewer than two
    agents have one (no rank distribution to speak of).
    """
    rows = (
        await session.execute(
            text(
                """
                WITH latest AS (
                    SELECT s.agent_id, s.value,
                           ROW_NUMBER() OVER (
                               PARTITION BY s.agent_id ORDER BY s.captured_at DESC
                           ) AS rn
                    FROM signals s
                    JOIN agents a ON a.id = s.agent_id
                    WHERE s.source = CAST('openrouter_token_volume_30d' AS signal_source)
                      AND a.eligibility_status = 'admitted'
                      AND a.entity_kind = 'foundation_model'
                      AND s.captured_at > now() - interval '7 days'
                )
                SELECT agent_id, value
                FROM latest
                WHERE rn = 1
                ORDER BY value DESC
                """
            )
        )
    ).all()
    if len(rows) < 2:
        return None
    for idx, r in enumerate(rows, start=1):
        if r.agent_id == agent_id:
            return {
                "rank": idx,
                "total": len(rows),
                "tokens_30d": float(r.value),
            }
    return None


async def _agent_tags(session: AsyncSession, agent_id: UUID) -> list[dict[str, str]]:
    rows = await session.execute(
        text(
            """
            SELECT t.kind, t.value, t.display_name
            FROM agent_tags at JOIN tags t ON t.id = at.tag_id
            WHERE at.agent_id = :id
            ORDER BY t.kind, t.value
            """
        ),
        {"id": agent_id},
    )
    return [{"kind": r.kind, "value": r.value, "display_name": r.display_name} for r in rows]


# --------------------------------------------------------------- signals


async def signals_for_agent(
    session: AsyncSession,
    *,
    agent_id: UUID,
    sources: list[str] | None,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"id": agent_id, "since": since, "limit": limit}
    where = ["agent_id = :id", "captured_at >= :since"]
    if sources:
        where.append("source = ANY(CAST(:srcs AS signal_source[]))")
        params["srcs"] = sources
    sql = f"""
        SELECT source, captured_at, value
        FROM signals
        WHERE {' AND '.join(where)}
        ORDER BY source, captured_at ASC
        LIMIT :limit
    """
    rows = await session.execute(text(sql), params)
    series: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        series.setdefault(r.source, []).append(
            {"captured_at": r.captured_at, "value": float(r.value)}
        )
    return [{"source": k, "points": v} for k, v in series.items()]


# --------------------------------------------------------------- score history


async def agent_score_history(
    session: AsyncSession, *, agent_id: UUID, since: datetime, limit: int
) -> list[dict[str, Any]]:
    """Full pillar timeseries for one agent — fed into /agents/<slug>'s
    breakdown chart and the /compare overlay. Returns every pillar so a
    reader can see WHICH pillar moved when the headline moved."""
    rows = await session.execute(
        text(
            """
            SELECT computed_at, agent_score, adoption, quality, momentum, community
            FROM scores
            WHERE agent_id = :id AND computed_at >= :since
            ORDER BY computed_at ASC
            LIMIT :limit
            """
        ),
        {"id": agent_id, "since": since, "limit": limit},
    )
    return [
        {
            "captured_at": r.computed_at,
            "agent_score": float(r.agent_score),
            "adoption": float(r.adoption) if r.adoption is not None else None,
            "quality": float(r.quality) if r.quality is not None else None,
            "momentum": float(r.momentum) if r.momentum is not None else None,
            "community": float(r.community) if r.community is not None else None,
        }
        for r in rows
    ]


# --------------------------------------------------------------- benchmarks


async def benchmarks_for_agent(
    session: AsyncSession, agent_id: UUID
) -> list[dict[str, Any]]:
    sql = """
        WITH latest AS (
            SELECT br.benchmark_id, br.score, br.captured_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY br.benchmark_id ORDER BY br.captured_at DESC
                   ) AS rn
            FROM benchmark_results br
            WHERE br.agent_id = :id
        )
        SELECT b.id AS benchmark_id, b.name AS benchmark_name, b.max_score,
               l.captured_at, l.score
        FROM latest l JOIN benchmarks b ON b.id = l.benchmark_id
        WHERE l.rn = 1
        ORDER BY b.name
    """
    rows = await session.execute(text(sql), {"id": agent_id})
    return [
        {
            "benchmark_id": r.benchmark_id,
            "benchmark_name": r.benchmark_name,
            "captured_at": r.captured_at,
            "score": float(r.score),
            "max_score": float(r.max_score) if r.max_score is not None else None,
        }
        for r in rows
    ]


# --------------------------------------------------------------- similar (vibe)


async def similar_agents(
    session: AsyncSession, *, agent_id: UUID, limit: int
) -> list[dict[str, Any]]:
    """pgvector cosine. Returns [] when source agent has no embedding."""
    has_embedding = await session.execute(
        text("SELECT embedding IS NOT NULL FROM agents WHERE id = :id"),
        {"id": agent_id},
    )
    flag = has_embedding.scalar_one_or_none()
    if not flag:
        return []
    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS},
               1 - (a.embedding <=> base.embedding) AS similarity
        FROM agents base, agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        WHERE base.id = :id
          AND a.id != :id
          AND a.eligibility_status = 'admitted'
          AND a.embedding IS NOT NULL
        ORDER BY base.embedding <=> a.embedding ASC
        LIMIT :limit
    """
    rows = await session.execute(text(sql), {"id": agent_id, "limit": limit})
    out: list[dict[str, Any]] = []
    for r in rows:
        sim = _row_to_agent_summary(r)
        out.append({"agent": sim, "similarity": float(r.similarity)})
    return out


# --------------------------------------------------------------- indexes


async def list_indexes(session: AsyncSession) -> list[dict[str, Any]]:
    sql = """
        SELECT i.id, i.slug, i.name, i.methodology_md, i.rebalance_frequency,
               COALESCE(m.cnt, 0) AS members_count,
               (
                   SELECT composite_value FROM index_snapshots s
                   WHERE s.index_id = i.id
                   ORDER BY s.captured_at DESC LIMIT 1
               ) AS composite_value
        FROM indexes i
        LEFT JOIN (
            SELECT index_id, count(*) AS cnt FROM index_members
            WHERE removed_at IS NULL GROUP BY index_id
        ) m ON m.index_id = i.id
        ORDER BY i.slug
    """
    rows = await session.execute(text(sql))
    return [
        {
            "id": r.id,
            "slug": r.slug,
            "name": r.name,
            "methodology_md": r.methodology_md,
            "rebalance_frequency": r.rebalance_frequency,
            "members_count": int(r.members_count),
            "composite_value": (
                float(r.composite_value) if r.composite_value is not None else None
            ),
        }
        for r in rows
    ]


async def get_index_detail(
    session: AsyncSession, slug: str
) -> dict[str, Any] | None:
    base_sql = """
        SELECT i.id, i.slug, i.name, i.methodology_md, i.rebalance_frequency,
               (
                   SELECT count(*) FROM index_members
                   WHERE index_id = i.id AND removed_at IS NULL
               ) AS members_count,
               (
                   SELECT composite_value FROM index_snapshots s
                   WHERE s.index_id = i.id
                   ORDER BY s.captured_at DESC LIMIT 1
               ) AS composite_value,
               (
                   SELECT max(run_at) FROM rebalances WHERE index_id = i.id
               ) AS last_rebalance_at
        FROM indexes i
        WHERE i.slug = :slug
    """
    row = (await session.execute(text(base_sql), {"slug": slug})).first()
    if row is None:
        return None

    members_sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS}, im.weight, im.added_at
        FROM index_members im
        JOIN agents a ON a.id = im.agent_id
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        WHERE im.index_id = :iid AND im.removed_at IS NULL
        ORDER BY cs.agent_score DESC NULLS LAST
    """
    member_rows = await session.execute(text(members_sql), {"iid": row.id})
    constituents = []
    for m in member_rows:
        constituents.append(
            {
                "agent": _row_to_agent_summary(m),
                "weight": float(m.weight),
                "added_at": m.added_at,
            }
        )

    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "methodology_md": row.methodology_md,
        "rebalance_frequency": row.rebalance_frequency,
        "members_count": int(row.members_count),
        "composite_value": (
            float(row.composite_value) if row.composite_value is not None else None
        ),
        "constituents": constituents,
        "last_rebalance_at": row.last_rebalance_at,
    }


async def index_history(
    session: AsyncSession, *, slug: str, since: datetime, limit: int
) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT s.captured_at, s.composite_value
            FROM index_snapshots s
            JOIN indexes i ON i.id = s.index_id
            WHERE i.slug = :slug AND s.captured_at >= :since
            ORDER BY s.captured_at ASC
            LIMIT :limit
            """
        ),
        {"slug": slug, "since": since, "limit": limit},
    )
    return [
        {"captured_at": r.captured_at, "composite_value": float(r.composite_value)}
        for r in rows
    ]


async def index_rebalances(
    session: AsyncSession, *, slug: str, limit: int
) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT r.id, r.run_at, r.additions, r.removals, r.weight_changes, r.narrative_md
            FROM rebalances r
            JOIN indexes i ON i.id = r.index_id
            WHERE i.slug = :slug
            ORDER BY r.run_at DESC
            LIMIT :limit
            """
        ),
        {"slug": slug, "limit": limit},
    )
    return [
        {
            "id": r.id,
            "run_at": r.run_at,
            "additions": r.additions,
            "removals": r.removals,
            "weight_changes": r.weight_changes,
            "narrative_md": r.narrative_md,
        }
        for r in rows
    ]


# --------------------------------------------------------------- movers


WINDOWS = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


async def movers(
    session: AsyncSession,
    *,
    window: str,
    limit: int,
    capability: str | None = None,
    deployment: str | None = None,
    entity_kind: str | None = None,
) -> list[dict[str, Any]]:
    delta = WINDOWS.get(window, timedelta(days=1))
    since = datetime.now(UTC) - delta

    # Optional tag/kind filters — joined into the deltas projection so they
    # apply BEFORE the limit, otherwise we'd silently truncate to <N matches.
    extra_joins = ""
    extra_where = ""
    params: dict[str, Any] = {"since": since, "limit": limit}
    if capability:
        extra_joins += (
            " JOIN agent_tags at_cap ON at_cap.agent_id = a.id"
            " JOIN tags t_cap ON t_cap.id = at_cap.tag_id"
            " AND t_cap.kind = 'capability' AND t_cap.value = :capability"
        )
        params["capability"] = capability
    if deployment:
        extra_joins += (
            " JOIN agent_tags at_dep ON at_dep.agent_id = a.id"
            " JOIN tags t_dep ON t_dep.id = at_dep.tag_id"
            " AND t_dep.kind = 'deployment' AND t_dep.value = :deployment"
        )
        params["deployment"] = deployment
    if entity_kind:
        extra_where += " AND a.entity_kind = :entity_kind"
        params["entity_kind"] = entity_kind

    # Bug fix: previously this CTE selected scores where
    # computed_at >= :since, then took the EARLIEST score in that
    # window as `then_score`. That measures change *within* the
    # window, not change *vs the start of the window* — and for an
    # agent with continuous 5-min ticks across the past 24h, those
    # are nearly identical numbers so delta ~= 0 for everyone, the
    # Floor's "Biggest 24h moves" filter (delta>0 / delta<0)
    # filters everything out, and the page renders empty.
    #
    # Correct comparison: now_score = latest score, then_score =
    # most-recent score on or before (now - window). Per-agent
    # LATERAL JOINs do this without a window-function CTE.
    sql = f"""
        WITH latest AS (
            SELECT DISTINCT ON (s.agent_id)
                s.agent_id,
                s.agent_score AS now_score,
                s.computed_at AS now_at
            FROM scores s
            ORDER BY s.agent_id, s.computed_at DESC
        )
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS},
               (l.now_score - past.then_score) AS delta,
               past.then_score
        FROM latest l
        JOIN agents a ON a.id = l.agent_id
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        JOIN LATERAL (
            SELECT s.agent_score AS then_score FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= :since
            ORDER BY s.computed_at DESC LIMIT 1
        ) past ON true
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        {extra_joins}
        WHERE a.eligibility_status = 'admitted'
          AND past.then_score IS NOT NULL
          AND l.now_score IS NOT NULL
        {extra_where}
        ORDER BY abs(l.now_score - past.then_score) DESC
        LIMIT :limit
    """
    rows = await session.execute(text(sql), params)
    return [
        {
            "agent": _row_to_agent_summary(r),
            "delta": float(r.delta),
            "score_now": float(r.agent_score) if r.agent_score is not None else 0.0,
            "score_at_window_start": (
                float(r.then_score) if r.then_score is not None else None
            ),
        }
        for r in rows
    ]


# --------------------------------------------------------------- search


async def text_search(
    session: AsyncSession,
    *,
    q: str,
    limit: int,
    tag_kind: str | None = None,
    tag_value: str | None = None,
) -> list[dict[str, Any]]:
    """Ranked text search.

    Relevance order, highest first:
      1. Name starts with the query   (Gemini → matches "Gemini X")
      2. Slug starts with the query
      3. Name contains the query
      4. Slug contains the query
      5. Description contains the query   (lowest — keeps fuzzy hits last)

    Ties break on AgentScore.

    When ``tag_kind`` and ``tag_value`` are passed, the result set is
    additionally restricted to agents carrying that tag — letting the
    /search page combine a free-text query with a sidebar facet
    instead of treating them as exclusive.
    """
    pattern = f"%{q}%"
    starts = f"{q}%"
    tag_filter_sql = ""
    params: dict[str, Any] = {"pattern": pattern, "starts": starts, "limit": limit}
    if tag_kind and tag_value:
        tag_filter_sql = (
            " AND a.id IN ("
            "   SELECT at.agent_id FROM agent_tags at"
            "   JOIN tags t ON t.id = at.tag_id"
            "   WHERE t.kind = :tag_kind AND t.value = :tag_value"
            " )"
        )
        params["tag_kind"] = tag_kind
        params["tag_value"] = tag_value
    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS}
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        WHERE a.eligibility_status = 'admitted'
          AND (a.slug ILIKE :pattern OR a.name ILIKE :pattern OR a.description ILIKE :pattern)
          {tag_filter_sql}
        ORDER BY
            CASE
                WHEN a.name ILIKE :starts THEN 1
                WHEN a.slug ILIKE :starts THEN 2
                WHEN a.name ILIKE :pattern THEN 3
                WHEN a.slug ILIKE :pattern THEN 4
                ELSE 5
            END ASC,
            cs.agent_score DESC NULLS LAST
        LIMIT :limit
    """
    rows = await session.execute(text(sql), params)
    return [
        {"agent": _row_to_agent_summary(r), "similarity": None}
        for r in rows
    ]


async def search_suggest(
    session: AsyncSession, *, q: str, limit: int
) -> list[dict[str, Any]]:
    """Fast autocomplete.

    Matches three layers, blended:
      1. Agent name/slug substring match (the original behaviour).
      2. Agents whose tags contain the query (e.g. typing "browser"
         surfaces every agent tagged "browser-automation").
      3. Tag suggestions themselves — clicking one jumps to a
         pre-filtered /search view, so capabilities are first-class.
    """
    pattern = f"%{q}%"
    starts = f"{q}%"

    # Reserve a couple of slots for tag suggestions; agents take
    # the rest. Tag suggestions help users discover whole capability
    # cohorts they didn't know existed.
    tag_limit = max(1, min(2, limit // 4))
    agent_limit = max(1, limit - tag_limit)

    sql = """
        WITH tag_hits AS (
            -- agents whose tag values match — boosts recall for
            -- queries like "browser" or "open source" that don't
            -- appear in the agent name.
            SELECT DISTINCT a.id
            FROM agents a
            JOIN agent_tags at ON at.agent_id = a.id
            JOIN tags t ON t.id = at.tag_id
            WHERE a.eligibility_status = 'admitted'
              AND t.value ILIKE :pattern
        )
        SELECT a.slug, a.name, a.entity_kind, a.description, cs.agent_score,
               CASE
                   WHEN a.name ILIKE :starts THEN 1
                   WHEN a.slug ILIKE :starts THEN 2
                   WHEN a.name ILIKE :pattern OR a.slug ILIKE :pattern THEN 3
                   ELSE 4  -- matched only via tag
               END AS match_rank
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        WHERE a.eligibility_status = 'admitted'
          AND (
              a.slug ILIKE :pattern
              OR a.name ILIKE :pattern
              OR a.id IN (SELECT id FROM tag_hits)
          )
        ORDER BY match_rank ASC, cs.agent_score DESC NULLS LAST
        LIMIT :limit
    """
    rows = await session.execute(
        text(sql),
        {"pattern": pattern, "starts": starts, "limit": agent_limit},
    )
    agent_hits = [
        {
            "kind": "agent",
            "slug": r.slug,
            "name": r.name,
            "entity_kind": r.entity_kind,
            "description": r.description,
            "agent_score": float(r.agent_score) if r.agent_score is not None else None,
        }
        for r in rows
    ]

    # Tag suggestions — pull the most popular matching tags.
    tag_sql = """
        SELECT t.kind, t.value, count(*) AS cnt
        FROM tags t
        JOIN agent_tags at ON at.tag_id = t.id
        JOIN agents a ON a.id = at.agent_id
        WHERE a.eligibility_status = 'admitted'
          AND t.value ILIKE :pattern
        GROUP BY t.kind, t.value
        ORDER BY cnt DESC
        LIMIT :limit
    """
    tag_rows = await session.execute(
        text(tag_sql), {"pattern": pattern, "limit": tag_limit}
    )
    tag_hits = [
        {
            "kind": "tag",
            "tag_kind": r.kind,
            "tag_value": r.value,
            "count": int(r.cnt),
        }
        for r in tag_rows
    ]

    # Tag rows surface above the lowest-ranked agent hits but never
    # eclipse a clean prefix match on the agent name.
    return agent_hits + tag_hits


async def vibe_search(
    session: AsyncSession, *, embedding: list[float], limit: int
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS},
               1 - (a.embedding <=> CAST(:v AS vector)) AS similarity
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        WHERE a.eligibility_status = 'admitted'
          AND a.embedding IS NOT NULL
        ORDER BY a.embedding <=> CAST(:v AS vector) ASC
        LIMIT :limit
    """
    rows = await session.execute(
        text(sql), {"v": str(embedding), "limit": limit}
    )
    return [
        {"agent": _row_to_agent_summary(r), "similarity": float(r.similarity)}
        for r in rows
    ]


async def facet_counts(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Returns {kind -> [{value, count}, ...]} across all admitted agents."""
    rows = await session.execute(
        text(
            """
            SELECT t.kind, t.value, count(*) AS cnt
            FROM agent_tags at
            JOIN tags t ON t.id = at.tag_id
            JOIN agents a ON a.id = at.agent_id
            WHERE a.eligibility_status = 'admitted'
            GROUP BY t.kind, t.value
            ORDER BY t.kind, cnt DESC, t.value
            """
        )
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r.kind, []).append({"value": r.value, "count": int(r.cnt)})
    return out


# --------------------------------------------------------------- tags / events


async def list_tags(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT t.kind, t.value, t.display_name, count(at.agent_id) AS cnt
            FROM tags t
            LEFT JOIN agent_tags at ON at.tag_id = t.id
            GROUP BY t.kind, t.value, t.display_name
            ORDER BY t.kind, cnt DESC, t.value
            """
        )
    )
    return [
        {
            "kind": r.kind,
            "value": r.value,
            "display_name": r.display_name,
            "count": int(r.cnt),
        }
        for r in rows
    ]


async def list_events(
    session: AsyncSession, *, kind: str | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    where = ""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if kind:
        where = "WHERE kind = CAST(:k AS event_kind)"
        params["k"] = kind
    rows = await session.execute(
        text(
            f"""
            SELECT id, kind, agent_id, payload, created_at
            FROM events {where}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    items = [
        {
            "id": r.id,
            "kind": r.kind,
            "agent_id": r.agent_id,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    total = (
        await session.execute(text(f"SELECT count(*) FROM events {where}"), params)
    ).scalar_one()
    return items, int(total)


async def recent_admissions(
    session: AsyncSession, *, limit: int
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT {AGENT_COLS}, {SCORE_COLS}, {SCORE_24H_COL}, {RANKS_COLS}
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        LEFT JOIN LATERAL (
            SELECT s.agent_score AS score_24h_ago FROM scores s
            WHERE s.agent_id = a.id AND s.computed_at <= now() - interval '24 hours'
            ORDER BY s.computed_at DESC LIMIT 1
        ) s24 ON true
        {RANKS_JOIN}
        WHERE a.eligibility_status = 'admitted'
        ORDER BY a.discovered_at DESC
        LIMIT :limit
    """
    rows = await session.execute(text(sql), {"limit": limit})
    return [_row_to_agent_summary(r) for r in rows]
