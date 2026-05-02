"""Test fixtures: real Postgres + a fake Redis client.

Same shape as discovery/ingestion conftests. The factories at the bottom
build a deterministic synthetic dataset (100 agents with signals) used
by the scoring + index tests.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

API_DIR = Path(__file__).resolve().parents[2] / "api"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer

    c = PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="agenttape",
        password="agenttape",
        dbname="agenttape_test",
    )
    c.start()
    try:
        yield c
    finally:
        c.stop()


def _sync_url(c) -> str:
    return c.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)


def _async_url(c) -> str:
    return _sync_url(c).replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture(scope="session")
def migrated_db(postgres_container):
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _sync_url(postgres_container))
    sys.path.insert(0, str(API_DIR / "src"))
    os.environ["DATABASE_URL"] = _sync_url(postgres_container)
    command.upgrade(cfg, "head")
    return postgres_container


@pytest_asyncio.fixture
async def engine(migrated_db) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(_async_url(migrated_db), pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=False)
async def _reset_data(engine: AsyncEngine):
    yield
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE rebalances, index_snapshots, index_members, indexes, "
            "events, scores, benchmark_results, benchmarks, signals, "
            "agent_tags, tags, discovery_candidates, agents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def settings_with_db(migrated_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _async_url(migrated_db))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    import scoring.db as sdb

    sdb._engine = None
    sdb._factory = None

    from scoring.config import get_settings
    return get_settings()


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    async def aclose(self) -> None:
        pass


@pytest.fixture
def redis_client() -> Any:
    return FakeRedis()


# ---------------------------------------------------------------- factories


async def make_agent(
    session,
    *,
    slug: str,
    name: str | None = None,
    license_value: str | None = None,
    capability_value: str | None = None,
    deployment_value: str | None = None,
    manipulation_flags: dict | None = None,
) -> uuid.UUID:
    aid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO agents (id, slug, name, discovered_via, eligibility_status, manipulation_flags)
            VALUES (:id, :slug, :name, 'github_search', 'admitted', CAST(:flags AS jsonb))
            """
        ),
        {
            "id": aid,
            "slug": slug,
            "name": name or slug,
            "flags": json.dumps(manipulation_flags) if manipulation_flags else None,
        },
    )
    for kind, value in (
        ("license", license_value),
        ("capability", capability_value),
        ("deployment", deployment_value),
    ):
        if value:
            await _attach_tag(session, aid, kind, value)
    await session.commit()
    return aid


async def _attach_tag(session, agent_id, kind: str, value: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO tags (id, kind, value, display_name)
            VALUES (gen_random_uuid(), CAST(:kind AS tag_kind), :value, :display)
            ON CONFLICT (kind, value) DO NOTHING
            """
        ),
        {"kind": kind, "value": value, "display": value.title()},
    )
    tag_id = (
        await session.execute(
            text(
                "SELECT id FROM tags WHERE kind = CAST(:kind AS tag_kind) AND value = :value"
            ),
            {"kind": kind, "value": value},
        )
    ).scalar_one()
    await session.execute(
        text(
            "INSERT INTO agent_tags (agent_id, tag_id) VALUES (:a, :t) ON CONFLICT DO NOTHING"
        ),
        {"a": agent_id, "t": tag_id},
    )


async def add_signal(
    session,
    agent_id: uuid.UUID,
    source: str,
    value: float,
    *,
    captured_at: datetime | None = None,
) -> None:
    ts = captured_at or datetime.now(UTC)
    await session.execute(
        text(
            """
            INSERT INTO signals (id, captured_at, agent_id, source, value)
            VALUES (gen_random_uuid(), :ts, :aid, CAST(:src AS signal_source), :val)
            """
        ),
        {"ts": ts, "aid": agent_id, "src": source, "val": value},
    )


async def add_benchmark_result(
    session,
    agent_id: uuid.UUID,
    benchmark_name: str,
    score: float,
) -> None:
    bid = (
        await session.execute(
            text(
                """
                INSERT INTO benchmarks (id, name)
                VALUES (gen_random_uuid(), :n)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """
            ),
            {"n": benchmark_name},
        )
    ).scalar_one()
    await session.execute(
        text(
            """
            INSERT INTO benchmark_results (agent_id, benchmark_id, captured_at, score)
            VALUES (:a, :b, now(), :s)
            """
        ),
        {"a": agent_id, "b": bid, "s": score},
    )
