"""Shared fixtures for realtime tests.

Brings up Postgres (with pgvector) via testcontainers, applies the
apps/api Alembic migrations, and points realtime's lazy session factory
at it. Redis is left for the WS roundtrip test, which runs a real
container.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
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
            "TRUNCATE TABLE events, rebalances, index_snapshots, index_members, "
            "indexes, scores, benchmark_results, benchmarks, signals, "
            "agent_tags, tags, discovery_candidates, agents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def settings_with_db(migrated_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _async_url(migrated_db))

    import realtime.db as rdb

    rdb._engine = None
    rdb._factory = None
    return None
