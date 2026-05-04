"""add entity_kind to agents

Revision ID: 0003_entity_kind
Revises: 0002_quality_nullable
Create Date: 2026-05-03

Foundation models become first-class stocks. They live in the same
``agents`` table as application agents but with a different ``entity_kind``
so the scoring weights, the sector indexes, and the UI can branch on it.

Allowed values:
    application      — the default; AutoGPT / crewai / browser-use style
    foundation_model — Claude / GPT / Llama / Gemini etc.
    framework        — libraries that aren't agents themselves but
                       enable them (langchain core, etc.)
    mcp_server       — MCP servers tracked as standalone stocks

We don't use a Postgres ENUM here because we expect the value set to
expand and a varchar+CHECK is cheaper to evolve than an ALTER TYPE.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_entity_kind"
down_revision = "0002_quality_nullable"
branch_labels = None
depends_on = None


ALLOWED = ("application", "foundation_model", "framework", "mcp_server")


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "entity_kind",
            sa.String(length=32),
            nullable=False,
            server_default="application",
        ),
    )
    op.create_check_constraint(
        "ck_agents_entity_kind",
        "agents",
        f"entity_kind IN ({', '.join(repr(v) for v in ALLOWED)})",
    )
    op.create_index("ix_agents_entity_kind", "agents", ["entity_kind"])


def downgrade() -> None:
    op.drop_index("ix_agents_entity_kind", table_name="agents")
    op.drop_constraint("ck_agents_entity_kind", "agents", type_="check")
    op.drop_column("agents", "entity_kind")
