from __future__ import annotations

from ingestion.sources.arxiv import ArxivIngestor
from ingestion.sources.base import AgentRow, Ingestor, SignalReading
from ingestion.sources.benchmarks import BenchmarksIngestor
from ingestion.sources.bluesky import BlueskyMentions7dIngestor
from ingestion.sources.citations import ArxivCitationsIngestor
from ingestion.sources.crates import CratesDownloads90dIngestor
from ingestion.sources.discord import DiscordMembersIngestor
from ingestion.sources.docker_hub import DockerHubPulls30dIngestor
from ingestion.sources.fm_leaderboards import FMLeaderboardsIngestor
from ingestion.sources.github import (
    GithubCommits7dIngestor,
    GithubContributorsIngestor,
    GithubForksIngestor,
    GithubStarsIngestor,
)
from ingestion.sources.github_issue_velocity import (
    GithubIssueCloseRate30dIngestor,
)
from ingestion.sources.github_mentions import GithubMentions7dIngestor
from ingestion.sources.github_releases import GithubReleases90dIngestor
from ingestion.sources.github_repos_using_model import (
    GithubReposUsingModelIngestor,
)
from ingestion.sources.github_response_time import (
    GithubFirstResponseHours30dIngestor,
)
from ingestion.sources.google_trends import GoogleTrendsScoreIngestor
from ingestion.sources.openrouter_usage import (
    OpenRouterTokenVolume30dIngestor,
)
from ingestion.sources.hackernews import HNMentions7dIngestor
from ingestion.sources.huggingface import (
    HFDownloads30dIngestor,
    HFLikesIngestor,
    HFTrendingRankIngestor,
)
from ingestion.sources.mastodon_mentions import MastodonMentions7dIngestor
from ingestion.sources.mcp import MCPRegistryListedIngestor
from ingestion.sources.news_mentions import NewsMentionsIngestor
from ingestion.sources.packages import NPMWeeklyIngestor, PyPIMonthlyIngestor
from ingestion.sources.producthunt import ProductHuntUpvotesIngestor
from ingestion.sources.reddit import (
    RedditMentions7dIngestor,
    RedditPoints7dIngestor,
)
from ingestion.sources.stackoverflow import StackOverflowQuestions7dIngestor
from ingestion.sources.wikipedia import WikipediaViews30dIngestor

__all__ = [
    "AgentRow",
    "ArxivCitationsIngestor",
    "ArxivIngestor",
    "BenchmarksIngestor",
    "BlueskyMentions7dIngestor",
    "CratesDownloads90dIngestor",
    "DiscordMembersIngestor",
    "DockerHubPulls30dIngestor",
    "FMLeaderboardsIngestor",
    "GithubCommits7dIngestor",
    "GithubContributorsIngestor",
    "GithubFirstResponseHours30dIngestor",
    "GithubForksIngestor",
    "GithubIssueCloseRate30dIngestor",
    "GithubMentions7dIngestor",
    "GithubReleases90dIngestor",
    "GithubReposUsingModelIngestor",
    "GithubStarsIngestor",
    "GoogleTrendsScoreIngestor",
    "HFDownloads30dIngestor",
    "HFLikesIngestor",
    "HFTrendingRankIngestor",
    "HNMentions7dIngestor",
    "Ingestor",
    "MastodonMentions7dIngestor",
    "MCPRegistryListedIngestor",
    "NewsMentionsIngestor",
    "NPMWeeklyIngestor",
    "OpenRouterTokenVolume30dIngestor",
    "ProductHuntUpvotesIngestor",
    "PyPIMonthlyIngestor",
    "RedditMentions7dIngestor",
    "RedditPoints7dIngestor",
    "SignalReading",
    "StackOverflowQuestions7dIngestor",
    "WikipediaViews30dIngestor",
]
