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

Revision ID: 0013_efficiency_view
Revises: 0012_efficiency_signals
Create Date: 2026-05-18

(Previous revision id was ``0013_efficiency_in_current_scores_view``
which is 41 characters and overflowed ``alembic_version.version_num``
which is ``VARCHAR(32)``. Shortened to ``0013_efficiency_view``.)
"""
from __future__ import annotations

from alembic import op


revision = "0013_efficiency_view"
down_revision = "0012_efficiency_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres ``CREATE OR REPLACE VIEW`` can only ADD columns to the
    # end of the view's column list — never reorder or change types.
    # The original 0001 view ended with ``manipulation_resistance``,
    # so ``efficiency`` MUST come after it. First attempt of this
    # migration put efficiency before manipulation_resistance and
    # failed with "cannot change name of view column" — Postgres
    # treats a reorder as a column rename.
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
            manipulation_resistance,
            efficiency
        FROM scores
        ORDER BY agent_id, computed_at DESC
        """
    )


def downgrade() -> None:
    # Revert to the 0001 view definition (no efficiency column).
    # Use DROP + CREATE because shrinking the column list isn't
    # allowed by CREATE OR REPLACE VIEW either.
    op.execute("DROP VIEW IF EXISTS current_scores")
    op.execute(
        """
        CREATE VIEW current_scores AS
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
