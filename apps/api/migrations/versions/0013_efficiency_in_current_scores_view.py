"""add efficiency to current_scores view

Migration 0012 added an ``efficiency`` column to ``scores``, but the
``current_scores`` view (defined in 0001) has an explicit column list
that doesn't include it. Views in Postgres are frozen at creation —
``SELECT DISTINCT ON (agent_id) col1, col2, ...`` doesn't pick up new
columns just because the underlying table grew one.

Result on prod: queries against ``current_scores`` that referenced
``cs.efficiency`` failed with ``column cs.efficiency does not
exist`` even though ``scores.efficiency`` was populated correctly.

This migration just CREATE-OR-REPLACE's the view with the same
column list plus ``efficiency`` appended. No data movement.

Revision ID: 0013_efficiency_in_current_scores_view
Revises: 0012_efficiency_signals
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op


revision = "0013_efficiency_in_current_scores_view"
down_revision = "0012_efficiency_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW current_scores AS
        SELECT DISTINCT ON (agent_id)
            agent_id,
            id                         AS score_id,
            computed_at,
            agent_score,
            adoption,
            quality,
            momentum,
            community,
            efficiency,
            manipulation_resistance
        FROM scores
        ORDER BY agent_id, computed_at DESC
        """
    )


def downgrade() -> None:
    # Revert to the 0001 view definition (no efficiency column).
    op.execute(
        """
        CREATE OR REPLACE VIEW current_scores AS
        SELECT DISTINCT ON (agent_id)
            agent_id,
            id                         AS score_id,
            computed_at,
            agent_score,
            adoption,
            quality,
            momentum,
            community,
            manipulation_resistance
        FROM scores
        ORDER BY agent_id, computed_at DESC
        """
    )
