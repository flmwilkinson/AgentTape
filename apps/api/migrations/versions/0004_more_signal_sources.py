"""add new signal sources

Revision ID: 0004_more_signal_sources
Revises: 0003_entity_kind
Create Date: 2026-05-04

Adds three new values to the ``signal_source`` Postgres ENUM so the
new ingestors (Bluesky search, Stack Overflow tag activity, Product
Hunt upvotes) can write rows without violating the type.

Postgres requires ``ALTER TYPE ... ADD VALUE`` to run outside a
transaction block, hence the autocommit guard.
"""
from __future__ import annotations

from alembic import op

revision = "0004_more_signal_sources"
down_revision = "0003_entity_kind"
branch_labels = None
depends_on = None


NEW_VALUES = (
    "bluesky_mentions_7d",
    "stackoverflow_questions_7d",
    "producthunt_upvotes",
)


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction.
    # Alembic provides this via the autocommit_block context manager.
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for an ENUM type. Removing a value is
    # only possible by recreating the type; not worth doing for a
    # forward-only schema. Leave the values in place on downgrade.
    pass
