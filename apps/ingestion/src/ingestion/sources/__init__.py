from __future__ import annotations

from ingestion.sources.arxiv import ArxivIngestor
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.benchmarks import BenchmarksIngestor
from ingestion.sources.bluesky import BlueskyMentions7dIngestor
from ingestion.sources.citations import ArxivCitationsIngestor
from ingestion.sources.fm_leaderboards import FMLeaderboardsIngestor
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
from ingestion.sources.producthunt import ProductHuntUpvotesIngestor
from ingestion.sources.reddit import (
    RedditMentions7dIngestor,
    RedditPoints7dIngestor,
)
from ingestion.sources.stackoverflow import StackOverflowQuestions7dIngestor

__all__ = [
    "AgentRow",
    "ArxivCitationsIngestor",
    "ArxivIngestor",
    "BenchmarksIngestor",
    "BlueskyMentions7dIngestor",
    "FMLeaderboardsIngestor",
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
    "ProductHuntUpvotesIngestor",
    "PyPIMonthlyIngestor",
    "RedditMentions7dIngestor",
    "RedditPoints7dIngestor",
    "SignalReading",
    "StackOverflowQuestions7dIngestor",
]
