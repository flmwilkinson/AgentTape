"""make pillar columns nullable

Revision ID: 0006_pillar_nullable
Revises: 0005_github_mentions
Create Date: 2026-05-05

The new unified scoring formula returns null when a pillar has no
contributing signals on file ("Unrated"). Adoption, Momentum and
Community were originally NOT NULL because the old z-score formula
always produced a number; the new formula deliberately doesn't, so
those columns need to permit NULL the same way Quality always has.
"""
from __future__ import annotations

from alembic import op

revision = "0006_pillar_nullable"
down_revision = "0005_github_mentions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("scores", "adoption", nullable=True)
    op.alter_column("scores", "momentum", nullable=True)
    op.alter_column("scores", "community", nullable=True)


def downgrade() -> None:
    op.alter_column("scores", "adoption", nullable=False)
    op.alter_column("scores", "momentum", nullable=False)
    op.alter_column("scores", "community", nullable=False)
