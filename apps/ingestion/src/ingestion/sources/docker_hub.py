"""Docker Hub pulls — adoption signal for self-hosted agents.

For agents that publish a Docker image, ``pull_count`` is a strong
adoption proxy: it can't be inflated by GitHub stars or HN drama,
and it tracks people actually deploying the thing somewhere. Free,
no auth, exact endpoint:

    GET https://hub.docker.com/v2/repositories/{owner}/{repo}/

Match key: ``agent.package_names["dockerhub"]`` set to "owner/repo".
Population of that field is the discovery service's responsibility —
we do not synthesise it here. Agents without it are silently skipped.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

API = "https://hub.docker.com/v2/repositories/{repo}/"


class DockerHubPulls30dIngestor(Ingestor):
    name: ClassVar[str] = "docker_pulls_30d"
    source: ClassVar[SignalSource] = SignalSource.DOCKER_PULLS_30D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        sem = asyncio.Semaphore(8)

        async def one(a: AgentRow) -> SignalReading | None:
            repo = (a.package_names or {}).get("dockerhub")
            if not repo or "/" not in repo:
                return None
            async with sem:
                count = await _pull_count(self._http, repo)
            if count is None:
                return None
            return SignalReading(
                agent_id=a.id,
                source=SignalSource.DOCKER_PULLS_30D,
                value=float(count),
                captured_at=datetime.now(UTC),
            )

        results = await asyncio.gather(*(one(a) for a in agents))
        return [r for r in results if r is not None]


async def _pull_count(http, repo: str) -> int | None:
    """Lifetime pull_count for the Docker Hub repo, or None on miss.

    Docker Hub does not expose a 30-day window in this endpoint — the
    field is lifetime cumulative. The signal name keeps the *_30d
    suffix for naming symmetry with hf_downloads_30d but the anchor
    is calibrated against lifetime totals (see scoring/compute.py).
    """
    try:
        r = await http.get(API.format(repo=repo))
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json() or {}
    except ValueError:
        return None
    pulls = data.get("pull_count")
    if pulls is None:
        return None
    try:
        return int(pulls)
    except (ValueError, TypeError):
        return None
