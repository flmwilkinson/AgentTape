from __future__ import annotations

from discovery.scouts.arxiv_scout import ArxivScout
from discovery.scouts.base import Candidate, Scout
from discovery.scouts.github_search import GithubSearchScout
from discovery.scouts.hf_trending import HFTrendingScout
from discovery.scouts.hn_firehose import HNFirehoseScout
from discovery.scouts.mcp_registries import MCPRegistriesScout
from discovery.scouts.package_search import PackageSearchScout

ALL_SCOUTS: list[type[Scout]] = [
    GithubSearchScout,
    HFTrendingScout,
    MCPRegistriesScout,
    HNFirehoseScout,
    ArxivScout,
    PackageSearchScout,
]

SCOUT_BY_NAME: dict[str, type[Scout]] = {cls.name: cls for cls in ALL_SCOUTS}

__all__ = [
    "ALL_SCOUTS",
    "ArxivScout",
    "Candidate",
    "GithubSearchScout",
    "HFTrendingScout",
    "HNFirehoseScout",
    "MCPRegistriesScout",
    "PackageSearchScout",
    "SCOUT_BY_NAME",
    "Scout",
]
