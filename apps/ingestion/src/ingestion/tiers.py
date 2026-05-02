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
    GithubCommits7dIngestor,
    GithubContributorsIngestor,
    GithubForksIngestor,
    GithubStarsIngestor,
    HFDownloads30dIngestor,
    HFLikesIngestor,
    HFTrendingRankIngestor,
    HNMentions7dIngestor,
    Ingestor,
    MCPRegistryListedIngestor,
    NPMWeeklyIngestor,
    PyPIMonthlyIngestor,
    RedditMentions7dIngestor,
    RedditPoints7dIngestor,
)

FAST: list[type[Ingestor]] = [
    GithubStarsIngestor,
    HNMentions7dIngestor,
    HFTrendingRankIngestor,
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
]

SLOW: list[type[Ingestor]] = [
    BenchmarksIngestor,
    ArxivCitationsIngestor,
    ArxivIngestor,
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
