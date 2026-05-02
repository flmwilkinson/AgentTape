from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base, TimestampMixin
from agenttape_api.db.enums import (
    PG_NAMES,
    DiscoverySource,
    DiscoveryVia,
    EligibilityStatus,
)


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    homepage_url: Mapped[str | None] = mapped_column(Text)

    github_repo: Mapped[str | None] = mapped_column(String(255))
    hf_org: Mapped[str | None] = mapped_column(String(255))
    hf_model_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    package_names: Mapped[dict | None] = mapped_column(JSONB)
    arxiv_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    discovered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    discovered_via: Mapped[DiscoveryVia] = mapped_column(
        Enum(DiscoveryVia, name=PG_NAMES[DiscoveryVia], create_type=False),
        nullable=False,
    )

    eligibility_status: Mapped[EligibilityStatus] = mapped_column(
        Enum(
            EligibilityStatus,
            name=PG_NAMES[EligibilityStatus],
            create_type=False,
        ),
        nullable=False,
        server_default=EligibilityStatus.PENDING.value,
    )
    eligibility_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    eligibility_reasons: Mapped[dict | None] = mapped_column(JSONB)
    last_admitted_check_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    manipulation_flags: Mapped[dict | None] = mapped_column(JSONB)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    __table_args__ = (
        Index("ix_agents_eligibility_status", "eligibility_status"),
        Index("ix_agents_discovered_at", "discovered_at"),
        Index("ix_agents_github_repo", "github_repo"),
    )


class DiscoveryCandidate(Base):
    """Holding pen: things `discovery` found but hasn't yet admitted as agents."""

    __tablename__ = "discovery_candidates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    source: Mapped[DiscoverySource] = mapped_column(
        Enum(DiscoverySource, name=PG_NAMES[DiscoverySource], create_type=False),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    found_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    promoted_to_agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Idempotent admission: same (source, source_id) seen twice is one row.
        Index(
            "uq_discovery_candidates_source_source_id",
            "source",
            "source_id",
            unique=True,
        ),
        Index("ix_discovery_candidates_found_at", "found_at"),
    )
