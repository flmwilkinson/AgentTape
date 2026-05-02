"""Promoter tests against a real Postgres with the apps/api schema applied.

We hand-insert candidates into ``discovery_candidates`` (skipping the scouts)
and verify the promoter:

- admits clearly-agent things
- rejects clearly-not-agent things
- leaves middling things in pending review
- creates an event row + tags + a unique slug
- is idempotent on retry
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from discovery.promoter import run_promoter, score_candidate

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("_reset_data")]


async def _insert_candidate(session, source: str, source_id: str, payload: dict) -> uuid.UUID:
    cid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO discovery_candidates (id, source, source_id, raw_payload)
            VALUES (:id, CAST(:source AS discovery_source), :sid, CAST(:payload AS jsonb))
            """
        ),
        {"id": cid, "source": source, "sid": source_id, "payload": json.dumps(payload)},
    )
    await session.commit()
    return cid


def test_score_admits_strong_signals():
    """40+20+20+10+10 = 1.0 max."""
    payload = {
        "name": "MyAgent",
        "description": "Autonomous multi-step agent using langchain to plan and use tools.",
        "stargazers_count": 500,
        "pushed_at": "2099-01-01T00:00:00Z",  # always recent enough
        "packaged": True,
    }
    score, reasons = score_candidate(payload, "github")
    assert score >= 0.6
    assert "llm_dep" in reasons


def test_score_rejects_unrelated_repo():
    payload = {
        "name": "todo-app",
        "description": "A simple todo list",
        "stargazers_count": 5,
    }
    score, _ = score_candidate(payload, "github")
    assert score < 0.4


async def test_promoter_admits_strong_candidate(session, settings_with_db):
    cid = await _insert_candidate(
        session,
        "github",
        "anthropics/agent-sdk",
        {
            "name": "agent-sdk",
            "full_name": "anthropics/agent-sdk",
            "description": "An autonomous LLM agent using langchain for tool use.",
            "stargazers_count": 5000,
            "pushed_at": "2099-01-01T00:00:00Z",
            "html_url": "https://github.com/anthropics/agent-sdk",
            "topics": ["ai-agent", "llm-agent"],
        },
    )

    result = await run_promoter(session, settings_with_db)
    assert result["admitted"] >= 1

    # Candidate is now linked to an agent.
    row = (
        await session.execute(
            text(
                "SELECT promoted_to_agent_id FROM discovery_candidates WHERE id = :id"
            ),
            {"id": cid},
        )
    ).first()
    assert row is not None and row[0] is not None
    agent_id = row[0]

    # Agent has admitted status, the discovered_via came from github,
    # and an event was emitted.
    agent = (
        await session.execute(
            text(
                "SELECT slug, eligibility_status, discovered_via, github_repo "
                "FROM agents WHERE id = :id"
            ),
            {"id": agent_id},
        )
    ).first()
    slug, status, via, github = agent
    assert status == "admitted"
    assert via == "github_search"
    assert github == "anthropics/agent-sdk"
    assert slug.startswith("agent-sdk")

    events = (
        await session.execute(
            text(
                "SELECT count(*) FROM events "
                "WHERE kind = 'agent_admitted' AND agent_id = :id"
            ),
            {"id": agent_id},
        )
    ).scalar_one()
    assert events == 1


async def test_promoter_rejects_weak_candidate(session, settings_with_db):
    cid = await _insert_candidate(
        session,
        "github",
        "user/todo-app",
        {
            "name": "todo-app",
            "description": "Simple CRUD app",
            "stargazers_count": 3,
        },
    )
    result = await run_promoter(session, settings_with_db)
    assert result["rejected"] >= 1

    rej = (
        await session.execute(
            text(
                "SELECT rejection_reason FROM discovery_candidates WHERE id = :id"
            ),
            {"id": cid},
        )
    ).scalar_one()
    assert rej is not None


async def test_promoter_is_idempotent(session, settings_with_db):
    """Re-running on the same candidate must not duplicate the agent."""
    payload = {
        "name": "agent-foo",
        "description": "Autonomous agent that uses anthropic tool-use to plan steps.",
        "stargazers_count": 200,
        "pushed_at": "2099-01-01T00:00:00Z",
    }
    await _insert_candidate(session, "github", "x/agent-foo", payload)
    await run_promoter(session, settings_with_db)
    # Add another candidate with the same slug-derived name from a different source.
    await _insert_candidate(session, "npm", "agent-foo", payload)
    await run_promoter(session, settings_with_db)

    cnt = (
        await session.execute(
            text("SELECT count(*) FROM agents WHERE slug = 'agent-foo'")
        )
    ).scalar_one()
    assert cnt == 1


async def test_pending_candidates_left_alone_when_in_grey_zone(
    session, settings_with_db
):
    # Score lands between 0.4 and 0.6: agent vocab + popularity floor only,
    # no LLM dep marker, not maintained, not packaged.
    cid = await _insert_candidate(
        session,
        "github",
        "x/grey-zone",
        {
            "name": "grey-zone",
            "description": "An agent for fun",
            "stargazers_count": 100,
        },
    )
    result = await run_promoter(session, settings_with_db)
    assert result["pending_review"] >= 1

    payload = (
        await session.execute(
            text("SELECT raw_payload FROM discovery_candidates WHERE id = :id"),
            {"id": cid},
        )
    ).scalar_one()
    assert payload["eligibility"]["decision"] == "pending_review"
    assert payload["eligibility"]["score"] >= 0.4
