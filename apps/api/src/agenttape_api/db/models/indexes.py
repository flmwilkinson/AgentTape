from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy import Index as SAIndex
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base


class Index(Base):
    """Index definitions: tape-100, code-25, web-25, oss-50, mcp-25, ..."""

    __tablename__ = "indexes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    methodology_md: Mapped[str | None] = mapped_column(Text)
    rebalance_frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    eligibility_rules: Mapped[dict | None] = mapped_column(JSONB)


class IndexMember(Base):
    __tablename__ = "index_members"

    index_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True, server_default=func.now()
    )
    weight: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        SAIndex("ix_index_members_index_active", "index_id", "removed_at"),
    )


class IndexSnapshot(Base):
    """Time-series of the whole index value, for charting."""

    __tablename__ = "index_snapshots"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    index_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    composite_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    constituents: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        SAIndex(
            "ix_index_snapshots_index_captured_desc",
            "index_id",
            "captured_at",
        ),
    )


class Rebalance(Base):
    __tablename__ = "rebalances"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    index_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    additions: Mapped[dict | None] = mapped_column(JSONB)
    removals: Mapped[dict | None] = mapped_column(JSONB)
    weight_changes: Mapped[dict | None] = mapped_column(JSONB)
    narrative_md: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        SAIndex("ix_rebalances_index_run", "index_id", "run_at"),
    )
