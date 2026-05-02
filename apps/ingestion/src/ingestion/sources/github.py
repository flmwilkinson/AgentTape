"""GitHub ingestors.

When ``GITHUB_TOKEN`` is set we batch up to 100 repos per GraphQL query,
which is the only realistic way to keep the FAST tier under 5 min for
hundreds of agents. Without a token we fall back to the REST endpoints
for stars/forks (slower, lower rate limit). Contributors and 7-day
commits use REST regardless because GraphQL doesn't expose a clean
"commits in the last 7 days" aggregate.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


def _split_repo(full_name: str) -> tuple[str, str] | None:
    if not full_name or "/" not in full_name:
        return None
    owner, repo = full_name.split("/", 1)
    return owner, repo


def _auth_headers(token: str | None) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# --------------------------------------------------------------- stars


class GithubStarsIngestor(Ingestor):
    name: ClassVar[str] = "github_stars"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_STARS
    tier: ClassVar[str] = "fast"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        repos = [(a, _split_repo(a.github_repo or "")) for a in agents]
        targets = [(a, owner_repo) for a, owner_repo in repos if owner_repo]
        if not targets:
            return []

        if self.settings.github_token:
            return await _batched_repo_query(
                self._http,
                self.settings.github_token,
                targets,
                fields=("stargazerCount",),
                map_field="stargazerCount",
                source=SignalSource.GITHUB_STARS,
            )
        return await _rest_per_repo(
            self._http, targets, "stargazers_count", SignalSource.GITHUB_STARS
        )


# --------------------------------------------------------------- forks


class GithubForksIngestor(Ingestor):
    name: ClassVar[str] = "github_forks"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_FORKS
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        targets = [
            (a, _split_repo(a.github_repo or ""))
            for a in agents
            if a.github_repo
        ]
        targets = [(a, t) for a, t in targets if t]
        if not targets:
            return []
        if self.settings.github_token:
            return await _batched_repo_query(
                self._http,
                self.settings.github_token,
                targets,
                fields=("forkCount",),
                map_field="forkCount",
                source=SignalSource.GITHUB_FORKS,
            )
        return await _rest_per_repo(
            self._http, targets, "forks_count", SignalSource.GITHUB_FORKS
        )


# --------------------------------------------------------- contributors


class GithubContributorsIngestor(Ingestor):
    """Distinct contributors in the past year (capped at 100 by REST API)."""

    name: ClassVar[str] = "github_contributors"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_CONTRIBUTORS
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        token = self.settings.github_token
        for a in agents:
            split = _split_repo(a.github_repo or "")
            if not split:
                continue
            owner, repo = split
            try:
                r = await self._http.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
                    params={"per_page": 100, "anon": "true"},
                    headers=_auth_headers(token),
                )
            except httpx.HTTPError as e:
                log.warning("contributors fetch failed for %s: %s", a.github_repo, e)
                continue
            if r.status_code != 200:
                continue
            data = r.json()
            count = len(data) if isinstance(data, list) else 0
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.GITHUB_CONTRIBUTORS,
                    value=float(count),
                    captured_at=datetime.now(UTC),
                )
            )
        return out


# ----------------------------------------------------- commits in 7 days


class GithubCommits7dIngestor(Ingestor):
    name: ClassVar[str] = "github_commits_7d"
    source: ClassVar[SignalSource] = SignalSource.GITHUB_COMMITS_7D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        token = self.settings.github_token
        since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        for a in agents:
            split = _split_repo(a.github_repo or "")
            if not split:
                continue
            owner, repo = split
            try:
                r = await self._http.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                    params={"since": since, "per_page": 100},
                    headers=_auth_headers(token),
                )
            except httpx.HTTPError:
                continue
            if r.status_code != 200:
                continue
            commits = r.json()
            count = len(commits) if isinstance(commits, list) else 0
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.GITHUB_COMMITS_7D,
                    value=float(count),
                    captured_at=datetime.now(UTC),
                )
            )
        return out


# ---------------------------------------------------------------- shared


async def _rest_per_repo(
    http: httpx.AsyncClient,
    targets: list[tuple[AgentRow, tuple[str, str]]],
    field: str,
    source: SignalSource,
) -> list[SignalReading]:
    out: list[SignalReading] = []
    semaphore = asyncio.Semaphore(8)

    async def fetch_one(a: AgentRow, owner_repo: tuple[str, str]) -> None:
        owner, repo = owner_repo
        async with semaphore:
            try:
                r = await http.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}",
                    headers={"Accept": "application/vnd.github+json"},
                )
            except httpx.HTTPError:
                return
        if r.status_code != 200:
            return
        data = r.json()
        if field not in data:
            return
        out.append(
            SignalReading(
                agent_id=a.id,
                source=source,
                value=float(data[field] or 0),
                captured_at=datetime.now(UTC),
            )
        )

    await asyncio.gather(*(fetch_one(a, t) for a, t in targets))
    return out


async def _batched_repo_query(
    http: httpx.AsyncClient,
    token: str,
    targets: list[tuple[AgentRow, tuple[str, str]]],
    fields: tuple[str, ...],
    map_field: str,
    source: SignalSource,
) -> list[SignalReading]:
    """One GraphQL call per 100 repos. Aliases let us pack many repos in a query."""
    field_block = " ".join(fields)
    out: list[SignalReading] = []
    for i in range(0, len(targets), 100):
        batch = targets[i : i + 100]
        parts = []
        agent_by_alias: dict[str, AgentRow] = {}
        for j, (a, (owner, repo)) in enumerate(batch):
            alias = f"r{j}"
            agent_by_alias[alias] = a
            parts.append(
                f'{alias}: repository(owner: "{owner}", name: "{repo}") '
                f"{{ {field_block} }}"
            )
        query = "query { " + " ".join(parts) + " }"
        try:
            r = await http.post(
                GITHUB_GRAPHQL,
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError:
            continue
        if r.status_code != 200:
            continue
        data: dict[str, Any] = r.json().get("data") or {}
        captured = datetime.now(UTC)
        for alias, agent in agent_by_alias.items():
            node = data.get(alias)
            if not node or map_field not in node:
                continue
            out.append(
                SignalReading(
                    agent_id=agent.id,
                    source=source,
                    value=float(node[map_field] or 0),
                    captured_at=captured,
                )
            )
    return out
