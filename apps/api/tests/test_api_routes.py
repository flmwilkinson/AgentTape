"""Smoke + integration tests for the REST API.

We use ``httpx.AsyncClient`` against the FastAPI ASGI app, backed by the
same testcontainer Postgres the schema tests use. Each route gets at
least one happy-path assertion; the agent + score paths get extra
assertions on the strict ScoreEnvelope shape.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from agenttape_api.main import app

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR / "src"))

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------- fixture seeding


async def _make_agent(session, slug: str) -> uuid.UUID:
    from sqlalchemy import text

    aid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, description, github_repo,
                                discovered_via, eligibility_status)
            VALUES (:id, :slug, :name, :desc, :repo, 'github_search', 'admitted')
            """
        ),
        {
            "id": aid,
            "slug": slug,
            "name": slug.replace("-", " ").title(),
            "desc": f"{slug}: a test agent for the API suite.",
            "repo": f"acme/{slug}",
        },
    )
    return aid


async def _add_score(session, aid, agent_score, *, quality=None):
    from sqlalchemy import text

    await session.execute(
        text(
            """
            INSERT INTO scores (id, agent_id, computed_at, agent_score, adoption,
                                quality, momentum, community, manipulation_resistance)
            VALUES (gen_random_uuid(), :id, now(), :a, :a, :q, :a, :a, 1.0)
            """
        ),
        {"id": aid, "a": agent_score, "q": quality},
    )


async def _add_signal(session, aid, source: str, value: float, *, ts=None):
    from sqlalchemy import text

    await session.execute(
        text(
            """
            INSERT INTO signals (id, captured_at, agent_id, source, value)
            VALUES (gen_random_uuid(), :ts, :id, CAST(:src AS signal_source), :v)
            """
        ),
        {"id": aid, "src": source, "v": value, "ts": ts or datetime.now(UTC)},
    )


@pytest.fixture
async def seed(session, settings_with_db):
    """Three agents with varying scores — enough to exercise sorting + paging."""
    from sqlalchemy import text

    a = await _make_agent(session, "alpha-agent")
    b = await _make_agent(session, "beta-agent")
    c = await _make_agent(session, "gamma-agent")
    await _add_score(session, a, 80.0, quality=70.0)
    await _add_score(session, b, 60.0, quality=None)  # unrated
    await _add_score(session, c, 40.0, quality=55.0)
    await _add_signal(session, a, "github_stars", 1000.0)
    await _add_signal(session, a, "github_stars", 1100.0, ts=datetime.now(UTC) + timedelta(seconds=1))

    # Initialize the five indexes (uses scoring service's ensure_indexes).
    await session.execute(
        text(
            """
            INSERT INTO indexes (id, slug, name, methodology_md,
                                 rebalance_frequency, eligibility_rules)
            VALUES (gen_random_uuid(), 'tape-100', 'TAPE-100', 'Top 100', 'weekly',
                    CAST('{"top_n": 100}' AS jsonb))
            ON CONFLICT (slug) DO NOTHING
            """
        )
    )
    await session.commit()
    return {"a": a, "b": b, "c": c}


@pytest.fixture
async def client(settings_with_db):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --------------------------------------------------------- meta + health


async def test_health_and_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    r = await client.get("/health")
    assert r.status_code == 200 and r.json()["service"] == "api"


async def test_openapi_schema_exposes_endpoints(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    paths = set(data["paths"].keys())
    expected = {
        "/agents",
        "/agents/{slug}",
        "/agents/{slug}/signals",
        "/agents/{slug}/benchmarks",
        "/agents/{slug}/similar",
        "/indexes",
        "/indexes/{slug}",
        "/indexes/{slug}/history",
        "/indexes/{slug}/rebalances",
        "/movers",
        "/search",
        "/tags",
        "/events",
        "/discovery/recent",
    }
    missing = expected - paths
    assert not missing, f"missing endpoints: {missing}"


# --------------------------------------------------------- agents


async def test_list_agents_paginated_and_sorted(client, seed):
    r = await client.get("/agents", params={"sort": "score", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 3
    slugs = [a["slug"] for a in data["items"][:3]]
    # Sorted by score desc — alpha (80) first.
    assert slugs[0] == "alpha-agent"


async def test_list_agents_filter_substring(client, seed):
    r = await client.get("/agents", params={"q": "alpha"})
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "alpha-agent"


async def test_agent_detail_envelope_shape(client, seed):
    """The strict rule: every agent response carries the full score envelope.

    We assert the keys explicitly so a future "headline only" sneak path
    can't pass tests silently.
    """
    r = await client.get("/agents/alpha-agent")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "alpha-agent"
    score = data["score"]
    expected_keys = {
        "agent_score",
        "adoption",
        "quality",
        "momentum",
        "community",
        "manipulation_resistance",
        "computed_at",
    }
    assert set(score.keys()) == expected_keys
    assert score["agent_score"] == 80.0


async def test_agent_with_unrated_quality_carries_null(client, seed):
    r = await client.get("/agents/beta-agent")
    score = r.json()["score"]
    assert score["quality"] is None
    assert score["agent_score"] == 60.0


async def test_agent_signals_time_series(client, seed):
    r = await client.get("/agents/alpha-agent/signals")
    assert r.status_code == 200
    series = r.json()
    sources = {s["source"] for s in series}
    assert "github_stars" in sources
    stars = next(s for s in series if s["source"] == "github_stars")
    assert len(stars["points"]) == 2
    # Ordered ascending by captured_at.
    assert stars["points"][0]["value"] == 1000.0


async def test_agent_404(client, seed):
    r = await client.get("/agents/does-not-exist")
    assert r.status_code == 404


async def test_agent_similar_returns_empty_without_embeddings(client, seed):
    r = await client.get("/agents/alpha-agent/similar")
    assert r.status_code == 200
    assert r.json() == []  # No agents have embeddings in this test DB.


# --------------------------------------------------------- indexes


async def test_list_indexes(client, seed):
    r = await client.get("/indexes")
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()]
    assert "tape-100" in slugs


async def test_index_detail_404(client, seed):
    r = await client.get("/indexes/nonexistent")
    assert r.status_code == 404


async def test_index_history_handles_empty(client, seed):
    r = await client.get("/indexes/tape-100/history")
    assert r.status_code == 200
    assert r.json() == []  # No snapshots yet.


# --------------------------------------------------------- search


async def test_text_search(client, seed):
    r = await client.get("/search", params={"q": "alpha"})
    assert r.status_code == 200
    data = r.json()
    assert any(h["agent"]["slug"] == "alpha-agent" for h in data["hits"])
    assert "facets" in data


async def test_vibe_search_falls_back_to_text_without_voyage_key(client, seed, monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    r = await client.get("/search", params={"q": "alpha", "mode": "vibe"})
    assert r.status_code == 200
    # Falls back to text search; alpha-agent should still show up.
    assert any(h["agent"]["slug"] == "alpha-agent" for h in r.json()["hits"])


# --------------------------------------------------------- movers / events


async def test_movers_returns_list(client, seed):
    r = await client.get("/movers", params={"window": "1d"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_events_endpoint_returns_paginated(client, seed):
    r = await client.get("/events", params={"limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data


async def test_tags_endpoint(client, seed):
    r = await client.get("/tags")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_discovery_recent(client, seed):
    r = await client.get("/discovery/recent", params={"limit": 5})
    assert r.status_code == 200
    items = r.json()
    assert all("score" in a for a in items)  # Every item carries the envelope.
