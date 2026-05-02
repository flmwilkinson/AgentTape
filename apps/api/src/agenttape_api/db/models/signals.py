from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base
from agenttape_api.db.enums import PG_NAMES, SignalSource


class Signal(Base):
    """Append-only time-series of measured signals.

    Partitioned by ``captured_at`` (RANGE, monthly). The migration creates the
    parent table with ``PARTITION BY RANGE (captured_at)`` and the partitions
    themselves; SQLAlchemy reads/writes the parent and the planner routes rows
    to the right partition automatically.
    """

    __tablename__ = "signals"

    # NOTE: The PK includes captured_at because Postgres requires the partition
    # key to be part of every UNIQUE constraint on a partitioned table.
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True, nullable=False
    )

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[SignalSource] = mapped_column(
        Enum(SignalSource, name=PG_NAMES[SignalSource], create_type=False),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)

    __table_args__ = (
        Index(
            "ix_signals_agent_source_captured_desc",
            "agent_id",
            "source",
            "captured_at",
        ),
        Index("ix_signals_source_captured_desc", "source", "captured_at"),
        # Tells SQLAlchemy this table is partitioned (Alembic emits the
        # PARTITION BY clause when used with create_table).
        {"postgresql_partition_by": "RANGE (captured_at)"},
    )
