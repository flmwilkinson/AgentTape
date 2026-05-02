from __future__ import annotations

from ingestion.sources.arxiv import ArxivIngestor
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.benchmarks import BenchmarksIngestor
from ingestion.sources.github import (
    GithubCommits7dIngestor,
    GithubContributorsIngestor,
    GithubForksIngestor,
    GithubStarsIngestor,
)
from ingestion.sources.hackernews import HNMentions7dIngestor
from ingestion.sources.huggingface import (
    HFDownloads30dIngestor,
    HFLikesIngestor,
    HFTrendingRankIngestor,
)
from ingestion.sources.mcp import MCPRegistryListedIngestor
from ingestion.sources.packages import NPMWeeklyIngestor, PyPIMonthlyIngestor
from ingestion.sources.reddit import (
    RedditMentions7dIngestor,
    RedditPoints7dIngestor,
)
from ingestion.sources.semantic_scholar import ArxivCitationsIngestor

__all__ = [
    "AgentRow",
    "ArxivCitationsIngestor",
    "ArxivIngestor",
    "BenchmarksIngestor",
    "GithubCommits7dIngestor",
    "GithubContributorsIngestor",
    "GithubForksIngestor",
    "GithubStarsIngestor",
    "HFDownloads30dIngestor",
    "HFLikesIngestor",
    "HFTrendingRankIngestor",
    "HNMentions7dIngestor",
    "Ingestor",
    "MCPRegistryListedIngestor",
    "NPMWeeklyIngestor",
    "PyPIMonthlyIngestor",
    "RedditMentions7dIngestor",
    "RedditPoints7dIngestor",
    "SignalReading",
]
