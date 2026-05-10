"""Tier registry — which ingestor classes belong to which tier.

The tier intervals come from settings so tests can crank them down.
Spec'd cadences:

    fast    every 5–15 min
    medium  every 1–6 hours
    slow    daily

We pick fast=5min, medium=60min, slow=24h as the sane defaults.
"""
from __future__ import annotations

from typing import ClassVar

from ingestion.sources import (
    ArxivCitationsIngestor,
    ArxivIngestor,
    BenchmarksIngestor,
    BlueskyMentions7dIngestor,
    CratesDownloads90dIngestor,
    DiscordMembersIngestor,
    DockerHubPulls30dIngestor,
    FMLeaderboardsIngestor,
    GithubCommits7dIngestor,
    GithubContributorsIngestor,
    GithubFirstResponseHours30dIngestor,
    GithubForksIngestor,
    GithubIssueCloseRate30dIngestor,
    GithubMentions7dIngestor,
    GithubReleases90dIngestor,
    GithubReposUsingModelIngestor,
    GithubStarsIngestor,
    GoogleTrendsScoreIngestor,
    HFDownloads30dIngestor,
    HFLikesIngestor,
    HFTrendingRankIngestor,
    HNMentions7dIngestor,
    Ingestor,
    MCPRegistryListedIngestor,
    NewsMentionsIngestor,
    NPMWeeklyIngestor,
    OpenRouterTokenVolume30dIngestor,
    ProductHuntUpvotesIngestor,
    PyPIMonthlyIngestor,
    RedditMentions7dIngestor,
    RedditPoints7dIngestor,
    StackOverflowQuestions7dIngestor,
    WikipediaViews30dIngestor,
)

FAST: list[type[Ingestor]] = [
    GithubStarsIngestor,
    HNMentions7dIngestor,
    HFTrendingRankIngestor,
    BlueskyMentions7dIngestor,
]

MEDIUM: list[type[Ingestor]] = [
    GithubForksIngestor,
    GithubContributorsIngestor,
    GithubCommits7dIngestor,
    HFLikesIngestor,
    HFDownloads30dIngestor,
    RedditPoints7dIngestor,
    RedditMentions7dIngestor,
    NPMWeeklyIngestor,
    PyPIMonthlyIngestor,
    MCPRegistryListedIngestor,
    StackOverflowQuestions7dIngestor,
    GithubMentions7dIngestor,
    # Migration 0007 — Priority A/B signal ingestors at the medium
    # cadence. They're either GitHub-token-rate-bounded (releases,
    # close-rate) or external API soft-rate (Docker, Crates, Discord).
    DockerHubPulls30dIngestor,
    CratesDownloads90dIngestor,
    GithubReleases90dIngestor,
    GithubIssueCloseRate30dIngestor,
    DiscordMembersIngestor,
    # OpenRouter token volume polled hourly — the rankings page
    # itself only updates every few hours but a stable cadence
    # gives the chart a clean tick.
    OpenRouterTokenVolume30dIngestor,
]

SLOW: list[type[Ingestor]] = [
    BenchmarksIngestor,
    ArxivCitationsIngestor,
    ArxivIngestor,
    ProductHuntUpvotesIngestor,
    FMLeaderboardsIngestor,
    # Wikipedia + Google Trends at slow tier — they don't move fast
    # enough to justify hourly polling, and Trends has its own
    # internal once-a-week gate.
    WikipediaViews30dIngestor,
    GoogleTrendsScoreIngestor,
    # First-response-hours is per-issue API-heavy (one comments fetch
    # per recent issue, capped at 30 issues × ~500 repos). Daily is
    # plenty given the underlying medians don't move that fast.
    GithubFirstResponseHours30dIngestor,
    # Cumulative count of GitHub repos referencing each FM. Slow
    # tier — the underlying number doesn't churn faster than daily,
    # and the GitHub Code Search API is the slowest of our github
    # endpoints (30 req/min authenticated).
    GithubReposUsingModelIngestor,
    # News mentions across a curated set of tech-news RSS feeds.
    # Slow because the feeds only refresh ~daily and the signal
    # ("is this in the news") doesn't move minute-to-minute.
    NewsMentionsIngestor,
]


class TierName:
    FAST: ClassVar[str] = "fast"
    MEDIUM: ClassVar[str] = "medium"
    SLOW: ClassVar[str] = "slow"


TIERS: dict[str, list[type[Ingestor]]] = {
    TierName.FAST: FAST,
    TierName.MEDIUM: MEDIUM,
    TierName.SLOW: SLOW,
}

INGESTOR_BY_NAME: dict[str, type[Ingestor]] = {
    cls.name: cls for tier in TIERS.values() for cls in tier
}
