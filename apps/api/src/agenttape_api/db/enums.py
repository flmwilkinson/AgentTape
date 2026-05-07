"""Domain enums.

The Postgres ENUM types are created in the initial migration; each Python
enum maps to a Postgres type via ``PG_NAMES``.
"""
from __future__ import annotations

import enum


class DiscoveryVia(str, enum.Enum):
    GITHUB_SEARCH = "github_search"
    HF_TRENDING = "hf_trending"
    MCP_REGISTRY = "mcp_registry"
    HN_SUBMISSION = "hn_submission"
    NPM_SEARCH = "npm_search"
    ARXIV_PAPER = "arxiv_paper"
    MANUAL = "manual"


class EligibilityStatus(str, enum.Enum):
    PENDING = "pending"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class DiscoverySource(str, enum.Enum):
    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    MCP_REGISTRY = "mcp_registry"
    HACKER_NEWS = "hacker_news"
    NPM = "npm"
    PYPI = "pypi"
    ARXIV = "arxiv"
    MANUAL = "manual"


class TagKind(str, enum.Enum):
    CAPABILITY = "capability"
    DOMAIN = "domain"
    LICENSE = "license"
    DEPLOYMENT = "deployment"
    MODEL_DEP = "model_dep"
    MATURITY = "maturity"


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
    # Added by migrations 0004 and 0005 — kept in sync with the
    # Postgres ENUM so SQLAlchemy doesn't reject values written by
    # the ingestion service.
    BLUESKY_MENTIONS_7D = "bluesky_mentions_7d"
    STACKOVERFLOW_QUESTIONS_7D = "stackoverflow_questions_7d"
    PRODUCTHUNT_UPVOTES = "producthunt_upvotes"
    GITHUB_MENTIONS_7D = "github_mentions_7d"
    # Migration 0007.
    DOCKER_PULLS_30D = "docker_pulls_30d"
    CRATES_DOWNLOADS_90D = "crates_downloads_90d"
    GITHUB_RELEASES_90D = "github_releases_90d"
    GITHUB_ISSUE_CLOSE_RATE_30D = "github_issue_close_rate_30d"
    WIKIPEDIA_VIEWS_30D = "wikipedia_views_30d"
    DISCORD_MEMBERS = "discord_members"
    GOOGLE_TRENDS_SCORE = "google_trends_score"
    # Migration 0008.
    OPENROUTER_TOKEN_VOLUME_30D = "openrouter_token_volume_30d"
    GITHUB_FIRST_RESPONSE_HOURS_30D = "github_first_response_hours_30d"


class EventKind(str, enum.Enum):
    AGENT_ADMITTED = "agent_admitted"
    SCORE_CHANGED = "score_changed"
    RANK_CHANGED = "rank_changed"
    INDEX_REBALANCED = "index_rebalanced"
    SIGNAL_SPIKE = "signal_spike"
    AGENT_FLAGGED = "agent_flagged"


# Postgres ENUM type names. The migration creates the types using these names
# and SQLAlchemy ``Enum(name=...)`` columns reference them.
PG_NAMES: dict[type[enum.Enum], str] = {
    DiscoveryVia: "discovery_via",
    EligibilityStatus: "eligibility_status",
    DiscoverySource: "discovery_source",
    TagKind: "tag_kind",
    SignalSource: "signal_source",
    EventKind: "event_kind",
}


def values(e: type[enum.Enum]) -> list[str]:
    return [m.value for m in e]
