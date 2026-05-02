"""SQLAlchemy bindings for the schema in apps/api/migrations/0001.

We don't run our own Alembic — apps/api owns the schema. This file just
gives us typed handles for the rows discovery reads/writes.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from discovery.enums import (
    DiscoverySource,
    DiscoveryVia,
    EligibilityStatus,
    EventKind,
)


class Base(DeclarativeBase):
    pass


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source: Mapped[DiscoverySource] = mapped_column(
        Enum(DiscoverySource, name="discovery_source", create_type=False),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    found_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    promoted_to_agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class Agent(Base):
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
        Enum(DiscoveryVia, name="discovery_via", create_type=False), nullable=False
    )
    eligibility_status: Mapped[EligibilityStatus] = mapped_column(
        Enum(EligibilityStatus, name="eligibility_status", create_type=False),
        nullable=False,
        server_default="pending",
    )
    eligibility_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    eligibility_reasons: Mapped[dict | None] = mapped_column(JSONB)
    last_admitted_check_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    manipulation_flags: Mapped[dict | None] = mapped_column(JSONB)
    # embedding (pgvector) is written via raw SQL; we don't bind it on the model.

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kind: Mapped[EventKind] = mapped_column(
        Enum(EventKind, name="event_kind", create_type=False), nullable=False
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL")
    )
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
