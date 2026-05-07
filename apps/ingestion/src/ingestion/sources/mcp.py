"""MCP registry presence — boolean per registry, summed.

We hit the two MCP registries once per slow tier tick and check whether
each agent's slug or github_repo appears in either. Value is the count
of registries listing it (0 or 2 today, but generalizes if more come
along).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


class MCPRegistryListedIngestor(Ingestor):
    name: ClassVar[str] = "mcp_registry_listed"
    source: ClassVar[SignalSource] = SignalSource.MCP_REGISTRY_LISTED
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        listed: set[str] = set()
        listed |= await _from_official(self._http)
        listed |= await _from_glama(self._http)

        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents:
            keys = {a.slug.lower()}
            if a.github_repo:
                keys.add(a.github_repo.lower())
            value = 1.0 if listed & keys else 0.0
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.MCP_REGISTRY_LISTED,
                    value=value,
                    captured_at=captured,
                )
            )
        return out


async def _from_official(http) -> set[str]:
    out: set[str] = set()
    cursor = None
    for _ in range(10):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            r = await http.get(
                "https://registry.modelcontextprotocol.io/v0/servers", params=params
            )
        except Exception:  # noqa: BLE001
            return out
        if r.status_code != 200:
            return out
        data = r.json() or {}
        for s in data.get("servers", []) or data.get("items", []):
            name = (s.get("name") or "").lower()
            if name:
                out.add(name)
            repo = (s.get("repository") or {})
            if isinstance(repo, dict):
                url = (repo.get("url") or "").lower()
                if "github.com/" in url:
                    out.add(url.split("github.com/", 1)[1].rstrip("/"))
        cursor = (data.get("metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return out


async def _from_glama(http) -> set[str]:
    out: set[str] = set()
    page = 1
    for _ in range(10):
        try:
            r = await http.get(
                "https://glama.ai/api/mcp/v1/servers",
                params={"page": page, "perPage": 100},
            )
        except Exception:  # noqa: BLE001
            return out
        if r.status_code != 200:
            return out
        data = r.json() or {}
        servers = data.get("servers") or data.get("data") or []
        if not servers:
            break
        for s in servers:
            slug = (s.get("slug") or s.get("name") or "").lower()
            if slug:
                out.add(slug)
            # Glama's API used to expose `repository` as a plain URL
            # string. It now returns either a string or an object
            # `{"url": "...", "source": "github"}` depending on the
            # server entry. Accept both shapes.
            repo_field = s.get("repository") or ""
            if isinstance(repo_field, dict):
                repo = (repo_field.get("url") or "").lower()
            else:
                repo = str(repo_field).lower()
            if "github.com/" in repo:
                out.add(repo.split("github.com/", 1)[1].rstrip("/"))
        page += 1
    return out
