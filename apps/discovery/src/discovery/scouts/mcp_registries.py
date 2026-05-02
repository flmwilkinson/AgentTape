"""MCP registry scout.

Pulls every server from the public MCP registries. Each MCP server is
itself an agent candidate.

Sources:
- https://registry.modelcontextprotocol.io/v0/servers (official registry)
- https://glama.ai/api/mcp/v1/servers (Glama's registry)

If a registry endpoint changes shape we log + skip rather than failing
the whole run; the other registry still produces candidates.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import ClassVar

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)


class MCPRegistriesScout(Scout):
    name: ClassVar[str] = "mcp_registries"
    interval_seconds: ClassVar[int] = 6 * 60 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        async for c in self._fetch_official():
            yield c
        async for c in self._fetch_glama():
            yield c

    async def _fetch_official(self) -> AsyncIterator[Candidate]:
        cursor: str | None = None
        for _ in range(10):  # cap pagination depth
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            r = await self._http.get(
                "https://registry.modelcontextprotocol.io/v0/servers", params=params
            )
            if r.status_code != 200:
                log.warning("mcp official registry returned %d", r.status_code)
                return
            data = r.json()
            servers = data.get("servers") or data.get("items") or []
            for s in servers:
                sid = s.get("name") or s.get("id")
                if not sid:
                    continue
                yield Candidate(
                    source=DiscoverySource.MCP_REGISTRY,
                    source_id=f"official:{sid}",
                    raw_payload={
                        "registry": "official",
                        "name": sid,
                        "description": s.get("description"),
                        "repository": s.get("repository"),
                        "version": s.get("version_detail") or s.get("version"),
                        "packages": s.get("packages"),
                        "remotes": s.get("remotes"),
                    },
                )
            cursor = (data.get("metadata") or {}).get("next_cursor")
            if not cursor:
                break

    async def _fetch_glama(self) -> AsyncIterator[Candidate]:
        page = 1
        for _ in range(10):
            r = await self._http.get(
                "https://glama.ai/api/mcp/v1/servers",
                params={"page": page, "perPage": 100},
            )
            if r.status_code != 200:
                log.warning("glama mcp returned %d", r.status_code)
                return
            data = r.json()
            servers = data.get("servers") or data.get("data") or []
            if not servers:
                break
            for s in servers:
                sid = s.get("slug") or s.get("name") or s.get("id")
                if not sid:
                    continue
                yield Candidate(
                    source=DiscoverySource.MCP_REGISTRY,
                    source_id=f"glama:{sid}",
                    raw_payload={
                        "registry": "glama",
                        "slug": sid,
                        "name": s.get("name"),
                        "description": s.get("description"),
                        "repository": s.get("repository"),
                        "homepage": s.get("homepage"),
                        "license": s.get("license"),
                        "tags": s.get("tags"),
                    },
                )
            page += 1
