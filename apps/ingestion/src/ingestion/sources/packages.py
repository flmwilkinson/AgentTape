"""npm + PyPI download counters."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


class NPMWeeklyIngestor(Ingestor):
    """npm exposes a public download-count endpoint with no auth."""

    name: ClassVar[str] = "npm_weekly"
    source: ClassVar[SignalSource] = SignalSource.NPM_WEEKLY
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        for a in agents:
            pkg = (a.package_names or {}).get("npm")
            if not pkg:
                continue
            try:
                r = await self._http.get(
                    f"https://api.npmjs.org/downloads/point/last-week/{pkg}"
                )
            except Exception:  # noqa: BLE001
                continue
            if r.status_code != 200:
                continue
            count = (r.json() or {}).get("downloads")
            if count is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.NPM_WEEKLY,
                    value=float(count),
                    captured_at=datetime.now(UTC),
                )
            )
        return out


class PyPIMonthlyIngestor(Ingestor):
    """PyPI doesn't ship download stats in its JSON; pypistats.org does."""

    name: ClassVar[str] = "pypi_monthly"
    source: ClassVar[SignalSource] = SignalSource.PYPI_MONTHLY
    tier: ClassVar[str] = "medium"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        out: list[SignalReading] = []
        for a in agents:
            pkg = (a.package_names or {}).get("pypi")
            if not pkg:
                continue
            try:
                r = await self._http.get(
                    f"https://pypistats.org/api/packages/{pkg}/recent"
                )
            except Exception:  # noqa: BLE001
                continue
            if r.status_code != 200:
                continue
            data = (r.json() or {}).get("data") or {}
            value = data.get("last_month")
            if value is None:
                continue
            out.append(
                SignalReading(
                    agent_id=a.id,
                    source=SignalSource.PYPI_MONTHLY,
                    value=float(value),
                    captured_at=datetime.now(UTC),
                )
            )
        return out
