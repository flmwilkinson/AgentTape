"""add OpenRouter token volume + GitHub first-response-hours signals

Revision ID: 0008_openrouter_response_time
Revises: 0007_signal_expansion
Create Date: 2026-05-07
"""
from __future__ import annotations

from alembic import op

revision = "0008_openrouter_response_time"
down_revision = "0007_signal_expansion"
branch_labels = None
depends_on = None


NEW_VALUES = (
    "openrouter_token_volume_30d",
    "github_first_response_hours_30d",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")


def downgrade() -> None:
    pass
