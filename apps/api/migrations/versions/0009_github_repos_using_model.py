"""add github_repos_using_model signal source

Revision ID: 0009_github_repos_using_model
Revises: 0008_openrouter_response_time
Create Date: 2026-05-09
"""
from __future__ import annotations

from alembic import op

revision = "0009_github_repos_using_model"
down_revision = "0008_openrouter_response_time"
branch_labels = None
depends_on = None


NEW_VALUES = ("github_repos_using_model",)


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
