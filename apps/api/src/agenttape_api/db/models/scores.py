from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base


class Score(Base):
    """One row per agent per recompute (NOT per day).

    The API reads from the ``current_scores`` view to get the latest row per
    agent without scanning history.
    """

    __tablename__ = "scores"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    agent_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    adoption: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    # Nullable: "Unrated" is its own state distinct from a low score
    # (see migration 0002_quality_nullable + apps/scoring/compute.py).
    quality: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    momentum: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    community: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    manipulation_resistance: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    __table_args__ = (
        # Critical: powers the current_scores view (DISTINCT ON (agent_id)
        # ORDER BY agent_id, computed_at DESC) and any "give me the latest
        # score for this agent" query.
        Index(
            "ix_scores_agent_computed_desc",
            "agent_id",
            "computed_at",
        ),
    )
