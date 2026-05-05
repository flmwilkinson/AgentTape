"""add github_mentions_7d signal source

Revision ID: 0005_github_mentions
Revises: 0004_more_signal_sources
Create Date: 2026-05-05

"GitHub mentions" — count of distinct repos referencing an agent or
model name in their code base over the past 7 days. The anchor signal
for "who is actually building on this", separate from the project's
own GitHub stars.
"""
from __future__ import annotations

from alembic import op

revision = "0005_github_mentions"
down_revision = "0004_more_signal_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE signal_source ADD VALUE IF NOT EXISTS 'github_mentions_7d'"
        )


def downgrade() -> None:
    # Postgres ENUMs don't support DROP VALUE.
    pass
