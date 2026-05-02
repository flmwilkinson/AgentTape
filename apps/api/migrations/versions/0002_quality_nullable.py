"""relax scores.quality to nullable

Revision ID: 0002_quality_nullable
Revises: 0001_initial_schema
Create Date: 2026-05-02

The scoring service emits ``quality = NULL`` for agents that don't appear
on any benchmark — the spec is explicit that "Unrated" is its own state,
distinct from a low score. The original schema declared it NOT NULL; this
flips that.
"""
from __future__ import annotations

from alembic import op

revision = "0002_quality_nullable"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scores ALTER COLUMN quality DROP NOT NULL")


def downgrade() -> None:
    # Restore by zero-filling existing NULLs first so the constraint can re-apply.
    op.execute("UPDATE scores SET quality = 0 WHERE quality IS NULL")
    op.execute("ALTER TABLE scores ALTER COLUMN quality SET NOT NULL")
