"""Hugging Face ingestors.

The HF API is anonymous-friendly for read-only model/space metadata.
Trending rank uses the global trending list — we look up an agent's
position by hf_id; agents not on the list get rank = 0 (still recorded
so the dashboard can show the gap).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)

HF_API = "https://huggingface.co/api"


def _auth_headers(token: str | None) -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _all_hf_ids(a: AgentRow) -> list[str]:
    return list(a.hf_model_ids or [])


# ---------------------------------------------------------- downloads


class HFDownloads30dIngestor(Ingestor):
    name: ClassVar[str] = "hf_downloads_30d"
    source: ClassVar[SignalSource] = SignalSource.HF_DOWNLOADS_30D
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        for a in agents:
            for hf_id in _all_hf_ids(a):
                value = await _hf_model_metric(
                    self._http, hf_id, self.settings.huggingface_token, "downloads"
                )
                if value is None:
                    continue
                out.append(
                    SignalReading(
                        agent_id=a.id,
                        source=SignalSource.HF_DOWNLOADS_30D,
                        value=float(value),
                        captured_at=datetime.now(UTC),
                    )
                )
        return out


class HFLikesIngestor(Ingestor):
    name: ClassVar[str] = "hf_likes"
    source: ClassVar[SignalSource] = SignalSource.HF_LIKES
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        for a in agents:
            for hf_id in _all_hf_ids(a):
                value = await _hf_model_metric(
                    self._http, hf_id, self.settings.huggingface_token, "likes"
                )
                if value is None:
                    continue
                out.append(
                    SignalReading(
                        agent_id=a.id,
                        source=SignalSource.HF_LIKES,
                        value=float(value),
                        captured_at=datetime.now(UTC),
                    )
                )
        return out


# ----------------------------------------------------- trending rank


class HFTrendingRankIngestor(Ingestor):
    """One HTTP call per tier tick: fetch the trending list, look agents up."""

    name: ClassVar[str] = "hf_trending_rank"
    source: ClassVar[SignalSource] = SignalSource.HF_TRENDING_RANK
    tier: ClassVar[str] = "fast"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        agents_with_hf = [a for a in agents if _all_hf_ids(a)]
        if not agents_with_hf:
            return []
        rank_by_id = await _fetch_trending_ranks(
            self._http, self.settings.huggingface_token
        )
        out: list[SignalReading] = []
        captured = datetime.now(UTC)
        for a in agents_with_hf:
            rank = 0  # 0 means "not on the trending list"
            for hf_id in _all_hf_ids(a):
                if hf_id in rank_by_id:
                    rank = rank_by_id[hf_id]
                    break
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.HF_TRENDING_RANK,
                    value=float(rank),
                    captured_at=captured,
                )
            )
        return out


# ---------------------------------------------------------------- helpers


async def _hf_model_metric(
    http, hf_id: str, token: str | None, field: str
) -> int | None:
    try:
        r = await http.get(
            f"{HF_API}/models/{hf_id}", headers=_auth_headers(token)
        )
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get(field)


async def _fetch_trending_ranks(http, token: str | None) -> dict[str, int]:
    try:
        r = await http.get(
            f"{HF_API}/models",
            params={"sort": "trendingScore", "direction": -1, "limit": 200},
            headers=_auth_headers(token),
        )
    except Exception:  # noqa: BLE001
        return {}
    if r.status_code != 200:
        return {}
    items = r.json() or []
    return {item.get("id"): i + 1 for i, item in enumerate(items) if item.get("id")}
