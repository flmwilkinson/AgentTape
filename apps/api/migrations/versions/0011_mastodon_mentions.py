"""add mastodon_mentions_7d signal source

Sister signal to bluesky_mentions_7d — counts public-search hits
across a curated set of large Mastodon instances. Captures the
FOSS-aligned half of the AI conversation that Bluesky doesn't
cover. Federated by design, so we hit a few big instances and
sum unique status URLs.

Revision ID: 0011_mastodon_mentions
Revises: 0010_news_mentions
Create Date: 2026-05-10
"""
from __future__ import annotations

from alembic import op

revision = "0011_mastodon_mentions"
down_revision = "0010_news_mentions"
branch_labels = None
depends_on = None


NEW_VALUES = ("mastodon_mentions_7d",)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")


def downgrade() -> None:
    pass
