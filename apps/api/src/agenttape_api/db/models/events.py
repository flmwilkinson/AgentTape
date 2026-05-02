from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base
from agenttape_api.db.enums import PG_NAMES, EventKind


class Event(Base):
    """The firehose used by the realtime layer."""

    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kind: Mapped[EventKind] = mapped_column(
        Enum(EventKind, name=PG_NAMES[EventKind], create_type=False), nullable=False
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_events_created_at_desc", "created_at"),
        Index("ix_events_kind_created", "kind", "created_at"),
    )
