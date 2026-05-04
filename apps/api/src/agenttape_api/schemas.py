"""Pydantic response schemas.

The single rule that dominates the design here: **every score field comes
bundled with all four pillars + manipulation_resistance + computed_at**,
and there is exactly one path that serializes a score (``ScoreEnvelope``).
There is no headline-only endpoint. If you find yourself writing
``{"agent_score": x.score}`` somewhere — stop and use this model instead.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- score


class ScoreEnvelope(BaseModel):
    """The only way to serialize a score on the wire.

    Always carries all four pillars. ``quality`` is nullable because
    "Unrated" is its own state distinct from a low score. ``score_24h_ago``
    and ``delta_24h`` are null when the agent has fewer than 24 hours of
    score history — the UI must distinguish "no data" from "zero change".
    """

    model_config = ConfigDict(extra="forbid")

    agent_score: float = Field(..., ge=0.0, le=100.0, description="Headline score 0-100")
    adoption: float = Field(..., ge=0.0, le=100.0)
    quality: float | None = Field(None, description="Null = Unrated; never 0 for unrated")
    momentum: float = Field(..., ge=0.0, le=100.0)
    community: float = Field(..., ge=0.0, le=100.0)
    manipulation_resistance: float = Field(..., ge=0.0, le=1.0)
    computed_at: datetime
    # 24-hour delta. Null = no history old enough to compare. Zero = compared
    # but unchanged. The UI must surface a "—" for null and an explicit "0"
    # or hidden chip for zero so users can tell them apart.
    score_24h_ago: float | None = None
    delta_24h: float | None = None
    # Global rank within entity_kind. 1 = top of the kind.
    # rank_delta_24h: positive number = climbed N positions in 24h.
    rank_now: int | None = None
    rank_24h_ago: int | None = None
    rank_delta_24h: int | None = None


class ScoreEnvelopeOptional(BaseModel):
    """Score envelope variant for endpoints where an agent may have no score yet."""

    model_config = ConfigDict(extra="forbid")

    agent_score: float | None = None
    adoption: float | None = None
    quality: float | None = None
    momentum: float | None = None
    community: float | None = None
    manipulation_resistance: float | None = None
    computed_at: datetime | None = None
    score_24h_ago: float | None = None
    delta_24h: float | None = None
    rank_now: int | None = None
    rank_24h_ago: int | None = None
    rank_delta_24h: int | None = None


# ---------------------------------------------------------------- agent


class TagOut(BaseModel):
    kind: str
    value: str
    display_name: str


class AgentSummary(BaseModel):
    """The compact form returned in /agents and /movers."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    slug: str
    name: str
    description: str | None
    discovered_via: str
    discovered_at: datetime
    homepage_url: str | None
    github_repo: str | None
    entity_kind: str = "application"
    score: ScoreEnvelopeOptional


class AgentDetail(AgentSummary):
    """The full /agents/:slug payload."""

    hf_org: str | None
    hf_model_ids: list[str] | None
    package_names: dict[str, Any] | None
    arxiv_ids: list[str] | None
    eligibility_status: str
    eligibility_score: float | None
    eligibility_reasons: dict[str, Any] | None
    manipulation_flags: dict[str, Any] | None
    tags: list[TagOut]
    # Source-of-truth metadata not on the row itself (e.g. OpenRouter
    # context_length, pricing, modality for foundation models).
    facts: dict[str, Any] = Field(default_factory=dict)


class SimilarAgent(BaseModel):
    agent: AgentSummary
    similarity: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------- signals / benchmarks


class SignalPoint(BaseModel):
    captured_at: datetime
    value: float


class SignalSeries(BaseModel):
    source: str
    points: list[SignalPoint]


class BenchmarkResultOut(BaseModel):
    benchmark_id: UUID
    benchmark_name: str
    captured_at: datetime
    score: float
    max_score: float | None


# ---------------------------------------------------------------- index


class IndexSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    methodology_md: str | None
    rebalance_frequency: str
    members_count: int
    composite_value: float | None


class IndexConstituent(BaseModel):
    agent: AgentSummary
    weight: float
    added_at: datetime


class IndexDetail(IndexSummary):
    constituents: list[IndexConstituent]
    last_rebalance_at: datetime | None


class IndexSnapshotOut(BaseModel):
    captured_at: datetime
    composite_value: float


class RebalanceOut(BaseModel):
    id: UUID
    run_at: datetime
    additions: list[dict[str, Any]] | None
    removals: list[dict[str, Any]] | None
    weight_changes: list[dict[str, Any]] | None
    narrative_md: str | None


# ---------------------------------------------------------------- mover / search / event


class MoverOut(BaseModel):
    agent: AgentSummary
    delta: float = Field(..., description="agent_score now minus agent_score at window-start")
    score_at_window_start: float | None
    score_now: float


class SearchHit(BaseModel):
    agent: AgentSummary
    similarity: float | None = None  # set on vibe-search


class FacetCount(BaseModel):
    value: str
    count: int


class SearchResult(BaseModel):
    hits: list[SearchHit]
    facets: dict[str, list[FacetCount]]


class EventOut(BaseModel):
    id: UUID
    kind: str
    agent_id: UUID | None
    payload: dict[str, Any] | None
    created_at: datetime


# ---------------------------------------------------------------- pagination


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Cursor-less offset paging — fine for the typical 100s-of-rows list size."""

    items: list[T]
    total: int
    limit: int
    offset: int
