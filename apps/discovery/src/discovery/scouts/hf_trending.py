"""Hugging Face trending scout.

Pulls trending Models and Spaces from the public HF API and filters for
agent-like tags. Public read endpoints work without auth; setting
HUGGINGFACE_TOKEN raises rate limits.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from discovery.enums import DiscoverySource
from discovery.scouts.base import Candidate, Scout

log = logging.getLogger(__name__)

HF_API = "https://huggingface.co/api"

AGENT_TAGS: set[str] = {
    "agents",
    "agentic",
    "agent",
    "tool-use",
    "tools",
    "function-calling",
    "browser-use",
    "llm-agent",
    "autonomous",
    "autonomous-agents",
}


class HFTrendingScout(Scout):
    name: ClassVar[str] = "hf_trending"
    interval_seconds: ClassVar[int] = 60 * 60

    async def discover(self) -> AsyncIterator[Candidate]:  # type: ignore[override]
        for kind, path in (("model", "/models"), ("space", "/spaces")):
            async for c in self._fetch(kind, path):
                yield c

    async def _fetch(self, kind: str, path: str) -> AsyncIterator[Candidate]:
        params = {"sort": "trendingScore", "direction": -1, "limit": 100, "full": "true"}
        headers = {"Accept": "application/json"}
        if self.settings.huggingface_token:
            headers["Authorization"] = f"Bearer {self.settings.huggingface_token}"
        r = await self._http.get(f"{HF_API}{path}", params=params, headers=headers)
        if r.status_code != 200:
            log.warning("hf %s returned %d", path, r.status_code)
            return
        items: list[dict[str, Any]] = r.json()
        for item in items:
            tags = {t.lower() for t in (item.get("tags") or [])}
            if not (tags & AGENT_TAGS):
                continue
            hf_id = item.get("id") or item.get("modelId")
            if not hf_id:
                continue
            yield Candidate(
                source=DiscoverySource.HUGGINGFACE,
                source_id=f"{kind}:{hf_id}",
                raw_payload={
                    "kind": kind,
                    "id": hf_id,
                    "author": item.get("author"),
                    "downloads": item.get("downloads"),
                    "likes": item.get("likes"),
                    "trendingScore": item.get("trendingScore"),
                    "tags": list(tags),
                    "pipeline_tag": item.get("pipeline_tag"),
                    "library_name": item.get("library_name"),
                    "lastModified": item.get("lastModified"),
                    "private": item.get("private"),
                    "html_url": f"https://huggingface.co/{hf_id}",
                },
            )
