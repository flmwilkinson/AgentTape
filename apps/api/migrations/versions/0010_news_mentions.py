"""add news_mentions_30d signal source

Counts mentions of an agent's name across a curated set of public
tech-news RSS feeds (TechCrunch, The Verge, VentureBeat, Ars Technica,
MIT Technology Review). Slow-tier; rolls up the most recent 30 days
of articles each tick.

Reads the same word-boundary token logic as benchmarks/arxiv so a
model named "GPT-5" picks up matches for "GPT-5" the article wrote,
not just for "openai-gpt-5" the slug we store internally.

Revision ID: 0010_news_mentions
Revises: 0009_github_repos_using_model
Create Date: 2026-05-10
"""
from __future__ import annotations

from alembic import op

revision = "0010_news_mentions"
down_revision = "0009_github_repos_using_model"
branch_labels = None
depends_on = None


NEW_VALUES = ("news_mentions_30d",)


def upgrade() -> None:
    # Postgres ENUM ALTERs cannot run inside a transaction block,
    # so we drop into autocommit for this migration.
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")


def downgrade() -> None:
    # Postgres ENUMs do not support removing values without rebuilding
    # the type. Leaving the value in place is harmless once it's not
    # being written or read.
    pass
