"""run_integrity_checks against a real Postgres: the merged flag set is
written whole, so exempt and expired entries actually disappear."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from ingestion.integrity import run_integrity_checks

pytestmark = pytest.mark.asyncio


async def _agent(session, *, kind: str, flags: dict | None) -> uuid.UUID:
    aid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, discovered_via, eligibility_status,
                                entity_kind, manipulation_flags)
            VALUES (:id, :slug, :name, 'github_search', 'admitted', :kind,
                    CAST(:flags AS jsonb))
            """
        ),
        {
            "id": aid,
            "slug": f"a-{aid.hex[:6]}",
            "name": "agent",
            "kind": kind,
            "flags": json.dumps(flags) if flags is not None else None,
        },
    )
    await session.commit()
    return aid


async def _flags(session, aid) -> dict | None:
    r = await session.execute(
        text("SELECT manipulation_flags FROM agents WHERE id = :id"), {"id": aid}
    )
    return r.scalar_one()


async def test_integrity_drops_exempt_and_expired_flags(
    session, settings_with_db, redis_client
):
    now = datetime.now(UTC)
    fm = await _agent(
        session,
        kind="foundation_model",
        flags={"coordinated_hn_posting": {"reason": "launch", "captured_at": now.isoformat()}},
    )
    stale = await _agent(
        session,
        kind="application",
        flags={
            "hf_surge_no_github": {
                "reason": "old", "captured_at": (now - timedelta(days=30)).isoformat(),
            },
            "star_spike_no_contrib_diversity": {
                "reason": "recent", "captured_at": (now - timedelta(days=1)).isoformat(),
            },
        },
    )
    clean = await _agent(session, kind="application", flags=None)

    await run_integrity_checks(session, redis_client, settings_with_db)

    assert await _flags(session, fm) is None
    assert set(await _flags(session, stale)) == {"star_spike_no_contrib_diversity"}
    assert await _flags(session, clean) is None
