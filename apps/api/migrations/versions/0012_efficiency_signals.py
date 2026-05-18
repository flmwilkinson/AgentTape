"""add Efficiency pillar — price/speed signals + scores column

Two FM-only signals sourced from the Artificial Analysis API (the
canonical reference for LLM cost + speed):

* openrouter_price_blended — mean of input + output $/M tokens,
  inverse-anchored so cheaper scores higher. The "openrouter"
  prefix reflects the longer-term plan to source from OpenRouter
  directly too; AA is the current pragmatic source.
* output_tokens_per_second — median throughput, higher = better.

These feed the new ``efficiency`` pillar — a 5th pillar on FMs
(applications stay at 4 pillars). Scores get a new ``efficiency``
column to store its per-agent value alongside the existing
adoption/quality/momentum/community.

Foundation-model AgentScore weights rebalance to:
    Adoption 25% · Quality 35% · Efficiency 20% · Momentum 10% ·
    Community 10%. Sums to 1.0.

Revision ID: 0012_efficiency_signals
Revises: 0011_mastodon_mentions
Create Date: 2026-05-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0012_efficiency_signals"
down_revision = "0011_mastodon_mentions"
branch_labels = None
depends_on = None


NEW_VALUES = (
    "openrouter_price_blended",
    "output_tokens_per_second",
)


def upgrade() -> None:
    # Add the new signal_source enum values. autocommit_block because
    # ALTER TYPE ADD VALUE can't run inside a transaction.
    with op.get_context().autocommit_block():
        for v in NEW_VALUES:
            op.execute(f"ALTER TYPE signal_source ADD VALUE IF NOT EXISTS '{v}'")

    # Add the efficiency column to scores. Nullable for two reasons:
    # (a) historical rows that don't have an efficiency value, and
    # (b) applications which legitimately never have one (5th pillar
    # is FM-only). Same nullable treatment as quality.
    op.add_column(
        "scores",
        sa.Column("efficiency", sa.Numeric(8, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scores", "efficiency")
