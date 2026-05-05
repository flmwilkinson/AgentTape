"""Mirror of the Postgres ENUMs in apps/api migration 0001."""
from __future__ import annotations

import enum


class SignalSource(str, enum.Enum):
    GITHUB_STARS = "github_stars"
    GITHUB_FORKS = "github_forks"
    GITHUB_COMMITS_7D = "github_commits_7d"
    GITHUB_CONTRIBUTORS = "github_contributors"
    HF_DOWNLOADS_30D = "hf_downloads_30d"
    HF_LIKES = "hf_likes"
    HF_TRENDING_RANK = "hf_trending_rank"
    NPM_WEEKLY = "npm_weekly"
    PYPI_MONTHLY = "pypi_monthly"
    MCP_REGISTRY_LISTED = "mcp_registry_listed"
    HN_POINTS_7D = "hn_points_7d"
    HN_MENTIONS_7D = "hn_mentions_7d"
    REDDIT_POINTS_7D = "reddit_points_7d"
    REDDIT_MENTIONS_7D = "reddit_mentions_7d"
    BENCHMARK_SCORE = "benchmark_score"
    ARXIV_CITATIONS = "arxiv_citations"
    BLUESKY_MENTIONS_7D = "bluesky_mentions_7d"
    STACKOVERFLOW_QUESTIONS_7D = "stackoverflow_questions_7d"
    PRODUCTHUNT_UPVOTES = "producthunt_upvotes"
    GITHUB_MENTIONS_7D = "github_mentions_7d"


class EventKind(str, enum.Enum):
    AGENT_ADMITTED = "agent_admitted"
    SCORE_CHANGED = "score_changed"
    RANK_CHANGED = "rank_changed"
    INDEX_REBALANCED = "index_rebalanced"
    SIGNAL_SPIKE = "signal_spike"
    AGENT_FLAGGED = "agent_flagged"


# Pillar -> signal sources mapping. Signals get added here so they
# actually contribute to the per-pillar score; if you add an
# ingestor without adding the source to the right pillar, the data
# accumulates in the signals table but never moves the score.
ADOPTION_SOURCES: list[SignalSource] = [
    SignalSource.GITHUB_STARS,
    SignalSource.HF_DOWNLOADS_30D,
    SignalSource.NPM_WEEKLY,
    SignalSource.PYPI_MONTHLY,
    SignalSource.MCP_REGISTRY_LISTED,
    SignalSource.STACKOVERFLOW_QUESTIONS_7D,
    SignalSource.PRODUCTHUNT_UPVOTES,
]

COMMUNITY_SOURCES: list[SignalSource] = [
    SignalSource.GITHUB_CONTRIBUTORS,
    SignalSource.HN_POINTS_7D,
    SignalSource.REDDIT_POINTS_7D,
    SignalSource.BLUESKY_MENTIONS_7D,
]

# For Momentum's rate-of-change.
MOMENTUM_SOURCES: list[SignalSource] = ADOPTION_SOURCES
