from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    max_score: Mapped[float | None] = mapped_column(Numeric(20, 6))
    last_scraped_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index("uq_benchmarks_name", "name", unique=True),
    )


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    benchmark_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("benchmarks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True, nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)

    __table_args__ = (
        Index(
            "ix_benchmark_results_agent_captured",
            "agent_id",
            "captured_at",
        ),
    )
