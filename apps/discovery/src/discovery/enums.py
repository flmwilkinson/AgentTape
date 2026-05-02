"""Mirrors the Postgres ENUM types created by apps/api migration 0001.

We re-declare them here so this service has its own self-contained schema
bindings; the migration is the source of truth.
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


class DiscoverySource(str, enum.Enum):
    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    MCP_REGISTRY = "mcp_registry"
    HACKER_NEWS = "hacker_news"
    NPM = "npm"
    PYPI = "pypi"
    ARXIV = "arxiv"
    MANUAL = "manual"


class EligibilityStatus(str, enum.Enum):
    PENDING = "pending"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class EventKind(str, enum.Enum):
    AGENT_ADMITTED = "agent_admitted"
    SCORE_CHANGED = "score_changed"
    RANK_CHANGED = "rank_changed"
    INDEX_REBALANCED = "index_rebalanced"
    SIGNAL_SPIKE = "signal_spike"
    AGENT_FLAGGED = "agent_flagged"


class TagKind(str, enum.Enum):
    CAPABILITY = "capability"
    DOMAIN = "domain"
    LICENSE = "license"
    DEPLOYMENT = "deployment"
    MODEL_DEP = "model_dep"
    MATURITY = "maturity"
