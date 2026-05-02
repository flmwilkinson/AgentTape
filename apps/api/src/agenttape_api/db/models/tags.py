from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agenttape_api.db.base import Base
from agenttape_api.db.enums import PG_NAMES, TagKind


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    kind: Mapped[TagKind] = mapped_column(
        Enum(TagKind, name=PG_NAMES[TagKind], create_type=False), nullable=False
    )
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        Index("uq_tags_kind_value", "kind", "value", unique=True),
    )


class AgentTag(Base):
    __tablename__ = "agent_tags"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
