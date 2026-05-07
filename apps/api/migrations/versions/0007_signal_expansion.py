"""add Priority A/B/C signal sources

Revision ID: 0007_signal_expansion
Revises: 0006_pillar_nullable
Create Date: 2026-05-07

Adds the signal_source enum values for the Priority A/B/C signal
expansion: Docker Hub pulls, Crates.io downloads, GitHub release
frequency / issue close rate, Wikipedia pageviews, Discord member
count, and Google Trends interest score.

Postgres requires ``ALTER TYPE ... ADD VALUE`` to run outside a
transaction, hence the autocommit guard.
"""
from __future__ import annotations

from alembic import op

revision = "0007_signal_expansion"
down_revision = "0006_pillar_nullable"
branch_labels = None
depends_on = None


NEW_VALUES = (
    "docker_pulls_30d",
    "crates_downloads_90d",
    "github_releases_90d",
    "github_issue_close_rate_30d",
    "wikipedia_views_30d",
    "discord_members",
    "google_trends_score",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for an ENUM type. Forward-only.
    pass
