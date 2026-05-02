"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-02

Creates the AgentTape schema in one shot:

- Extensions: pgcrypto + pgvector required, timescaledb best-effort.
- Enum types for discovery_via, eligibility_status, discovery_source,
  tag_kind, signal_source, event_kind.
- Core tables: agents, discovery_candidates, tags, agent_tags, signals,
  benchmarks, benchmark_results, scores, indexes, index_members,
  index_snapshots, rebalances, events.
- ``signals`` is RANGE-partitioned by ``captured_at`` (monthly). A helper
  function ``agenttape_create_signals_partition(month_start date)`` is
  installed for the ingestion service to call ahead of each new month.
  We pre-create partitions for last month, this month, and the next two
  months plus a DEFAULT partition for safety.
- View ``current_scores`` (DISTINCT ON agent_id, ordered by computed_at
  DESC). The API hits this constantly for "latest score per agent".
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


# ENUM definitions kept in one place so upgrade and downgrade agree.
ENUMS: dict[str, list[str]] = {
    "discovery_via": [
        "github_search",
        "hf_trending",
        "mcp_registry",
        "hn_submission",
        "npm_search",
        "arxiv_paper",
        "manual",
    ],
    "eligibility_status": ["pending", "admitted", "rejected", "deprecated"],
    "discovery_source": [
        "github",
        "huggingface",
        "mcp_registry",
        "hacker_news",
        "npm",
        "pypi",
        "arxiv",
        "manual",
    ],
    "tag_kind": [
        "capability",
        "domain",
        "license",
        "deployment",
        "model_dep",
        "maturity",
    ],
    "signal_source": [
        "github_stars",
        "github_forks",
        "github_commits_7d",
        "github_contributors",
        "hf_downloads_30d",
        "hf_likes",
        "hf_trending_rank",
        "npm_weekly",
        "pypi_monthly",
        "mcp_registry_listed",
        "hn_points_7d",
        "hn_mentions_7d",
        "reddit_points_7d",
        "reddit_mentions_7d",
        "benchmark_score",
        "arxiv_citations",
    ],
    "event_kind": [
        "agent_admitted",
        "score_changed",
        "rank_changed",
        "index_rebalanced",
        "signal_spike",
        "agent_flagged",
    ],
}


def _create_enums() -> None:
    for name, values in ENUMS.items():
        sa.Enum(*values, name=name).create(op.get_bind(), checkfirst=True)


def _drop_enums() -> None:
    for name in reversed(list(ENUMS)):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)


def _enum(name: str) -> postgresql.ENUM:
    """Reference an already-created Postgres ENUM type without re-creating it."""
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # --- extensions -----------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # TimescaleDB is optional; skip silently if the build doesn't have it.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
                CREATE EXTENSION IF NOT EXISTS timescaledb;
            END IF;
        END
        $$;
        """
    )

    # --- enums ----------------------------------------------------------
    _create_enums()

    # --- updated_at trigger function (used by agents) -------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION agenttape_set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # --- agents ---------------------------------------------------------
    # Created via raw SQL because pgvector's vector(1536) type isn't part of
    # upstream SQLAlchemy and we want it in the initial CREATE TABLE.
    op.execute(
        """
        CREATE TABLE agents (
            id                       uuid PRIMARY KEY,
            slug                     varchar(120) NOT NULL UNIQUE,
            name                     varchar(200) NOT NULL,
            description              text,
            homepage_url             text,
            github_repo              varchar(255),
            hf_org                   varchar(255),
            hf_model_ids             text[],
            package_names            jsonb,
            arxiv_ids                text[],
            discovered_at            timestamptz NOT NULL DEFAULT now(),
            discovered_via           discovery_via NOT NULL,
            eligibility_status       eligibility_status NOT NULL DEFAULT 'pending',
            eligibility_score        numeric(8, 4),
            eligibility_reasons      jsonb,
            last_admitted_check_at   timestamptz,
            manipulation_flags       jsonb,
            embedding                vector(1536),
            created_at               timestamptz NOT NULL DEFAULT now(),
            updated_at               timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index("ix_agents_eligibility_status", "agents", ["eligibility_status"])
    op.create_index("ix_agents_discovered_at", "agents", ["discovered_at"])
    op.create_index("ix_agents_github_repo", "agents", ["github_repo"])
    # IVFFlat ANN index for vibe / similar-agent search.
    op.execute(
        "CREATE INDEX ix_agents_embedding_cosine ON agents "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE TRIGGER trg_agents_set_updated_at BEFORE UPDATE ON agents "
        "FOR EACH ROW EXECUTE FUNCTION agenttape_set_updated_at()"
    )

    # --- discovery_candidates ------------------------------------------
    op.create_table(
        "discovery_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", _enum("discovery_source"), nullable=False),
        sa.Column("source_id", sa.String(512), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column(
            "found_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "promoted_to_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
        ),
        sa.Column("rejection_reason", sa.Text()),
    )
    op.create_index(
        "uq_discovery_candidates_source_source_id",
        "discovery_candidates",
        ["source", "source_id"],
        unique=True,
    )
    op.create_index(
        "ix_discovery_candidates_found_at", "discovery_candidates", ["found_at"]
    )

    # --- tags / agent_tags ---------------------------------------------
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", _enum("tag_kind"), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
    )
    op.create_index("uq_tags_kind_value", "tags", ["kind", "value"], unique=True)

    op.create_table(
        "agent_tags",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- signals (partitioned) -----------------------------------------
    # Native declarative partitioning, RANGE on captured_at, monthly.
    # The partition key MUST be part of any unique constraint, so the PK
    # is (id, captured_at).
    op.execute(
        """
        CREATE TABLE signals (
            id           uuid NOT NULL,
            captured_at  timestamptz NOT NULL,
            agent_id     uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            source       signal_source NOT NULL,
            value        numeric(20, 6) NOT NULL,
            PRIMARY KEY (id, captured_at)
        ) PARTITION BY RANGE (captured_at)
        """
    )
    op.create_index(
        "ix_signals_agent_source_captured_desc",
        "signals",
        ["agent_id", "source", sa.text("captured_at DESC")],
    )
    op.create_index(
        "ix_signals_source_captured_desc",
        "signals",
        ["source", sa.text("captured_at DESC")],
    )

    # Helper: create a monthly partition for the given month_start date.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION agenttape_create_signals_partition(month_start date)
        RETURNS void AS $$
        DECLARE
            partition_name text;
            range_start    text;
            range_end      text;
        BEGIN
            month_start    := date_trunc('month', month_start)::date;
            partition_name := format('signals_p%s', to_char(month_start, 'YYYYMM'));
            range_start    := to_char(month_start, 'YYYY-MM-DD');
            range_end      := to_char(month_start + interval '1 month', 'YYYY-MM-DD');

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF signals
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, range_start, range_end
            );
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # DEFAULT partition catches anything outside the explicit ranges.
    op.execute(
        "CREATE TABLE IF NOT EXISTS signals_default PARTITION OF signals DEFAULT"
    )

    # Pre-create partitions for last month, this month, and the next 2.
    op.execute(
        """
        DO $$
        DECLARE
            m date := date_trunc('month', now() - interval '1 month')::date;
            i int;
        BEGIN
            FOR i IN 0..3 LOOP
                PERFORM agenttape_create_signals_partition((m + (i || ' months')::interval)::date);
            END LOOP;
        END
        $$;
        """
    )

    # If TimescaleDB is loaded we still keep native partitioning for signals;
    # we leave a hint here that future migrations may opt into hypertables
    # for new time-series tables (e.g. ``index_snapshots``, ``events``).

    # --- benchmarks / benchmark_results --------------------------------
    op.create_table(
        "benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("category", sa.String(120)),
        sa.Column("max_score", sa.Numeric(20, 6)),
        sa.Column("last_scraped_at", postgresql.TIMESTAMP(timezone=True)),
    )
    op.create_index("uq_benchmarks_name", "benchmarks", ["name"], unique=True)

    op.create_table(
        "benchmark_results",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "benchmark_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("benchmarks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "captured_at",
            postgresql.TIMESTAMP(timezone=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(20, 6), nullable=False),
    )
    op.create_index(
        "ix_benchmark_results_agent_captured",
        "benchmark_results",
        ["agent_id", sa.text("captured_at DESC")],
    )

    # --- scores --------------------------------------------------------
    op.create_table(
        "scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "computed_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("agent_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("adoption", sa.Numeric(8, 4), nullable=False),
        sa.Column("quality", sa.Numeric(8, 4), nullable=False),
        sa.Column("momentum", sa.Numeric(8, 4), nullable=False),
        sa.Column("community", sa.Numeric(8, 4), nullable=False),
        sa.Column("manipulation_resistance", sa.Numeric(8, 4), nullable=False),
    )
    # Sort order matters: DISTINCT ON wants the leading prefix to match
    # ORDER BY (agent_id, computed_at DESC).
    op.execute(
        "CREATE INDEX ix_scores_agent_computed_desc "
        "ON scores (agent_id, computed_at DESC)"
    )

    # --- indexes / members / snapshots / rebalances --------------------
    op.create_table(
        "indexes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("methodology_md", sa.Text()),
        sa.Column("rebalance_frequency", sa.String(64), nullable=False),
        sa.Column("eligibility_rules", postgresql.JSONB()),
    )

    op.create_table(
        "index_members",
        sa.Column(
            "index_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("indexes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "added_at",
            postgresql.TIMESTAMP(timezone=True),
            primary_key=True,
            server_default=sa.text("now()"),
        ),
        sa.Column("weight", sa.Numeric(8, 6), nullable=False),
        sa.Column("removed_at", postgresql.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "ix_index_members_index_active", "index_members", ["index_id", "removed_at"]
    )

    op.create_table(
        "index_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "index_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("composite_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("constituents", postgresql.JSONB(), nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_index_snapshots_index_captured_desc "
        "ON index_snapshots (index_id, captured_at DESC)"
    )

    op.create_table(
        "rebalances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "index_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("additions", postgresql.JSONB()),
        sa.Column("removals", postgresql.JSONB()),
        sa.Column("weight_changes", postgresql.JSONB()),
        sa.Column("narrative_md", sa.Text()),
    )
    op.execute(
        "CREATE INDEX ix_rebalances_index_run "
        "ON rebalances (index_id, run_at DESC)"
    )

    # --- events --------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", _enum("event_kind"), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
        ),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX ix_events_created_at_desc ON events (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_events_kind_created ON events (kind, created_at DESC)"
    )

    # --- current_scores view -------------------------------------------
    # Returns one row per agent: the most recently computed score.
    # The API hits this constantly. Backed by ix_scores_agent_computed_desc.
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


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS current_scores")

    op.execute("DROP INDEX IF EXISTS ix_events_kind_created")
    op.execute("DROP INDEX IF EXISTS ix_events_created_at_desc")
    op.drop_table("events")

    op.execute("DROP INDEX IF EXISTS ix_rebalances_index_run")
    op.drop_table("rebalances")
    op.execute("DROP INDEX IF EXISTS ix_index_snapshots_index_captured_desc")
    op.drop_table("index_snapshots")
    op.drop_index("ix_index_members_index_active", table_name="index_members")
    op.drop_table("index_members")
    op.drop_table("indexes")

    op.execute("DROP INDEX IF EXISTS ix_scores_agent_computed_desc")
    op.drop_table("scores")

    op.drop_index("ix_benchmark_results_agent_captured", table_name="benchmark_results")
    op.drop_table("benchmark_results")
    op.drop_index("uq_benchmarks_name", table_name="benchmarks")
    op.drop_table("benchmarks")

    # signals: drop the parent table cascades to all partitions.
    op.execute("DROP FUNCTION IF EXISTS agenttape_create_signals_partition(date)")
    op.execute("DROP TABLE IF EXISTS signals CASCADE")

    op.drop_table("agent_tags")
    op.drop_index("uq_tags_kind_value", table_name="tags")
    op.drop_table("tags")

    op.drop_index(
        "ix_discovery_candidates_found_at", table_name="discovery_candidates"
    )
    op.drop_index(
        "uq_discovery_candidates_source_source_id", table_name="discovery_candidates"
    )
    op.drop_table("discovery_candidates")

    op.execute("DROP INDEX IF EXISTS ix_agents_embedding_cosine")
    op.drop_index("ix_agents_github_repo", table_name="agents")
    op.drop_index("ix_agents_discovered_at", table_name="agents")
    op.drop_index("ix_agents_eligibility_status", table_name="agents")
    op.execute("DROP TRIGGER IF EXISTS trg_agents_set_updated_at ON agents")
    op.execute("DROP FUNCTION IF EXISTS agenttape_set_updated_at()")
    op.drop_table("agents")

    _drop_enums()
