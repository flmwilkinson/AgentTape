"""Test fixtures spinning up a real Postgres (with pgvector) via testcontainers.

We deliberately do NOT mock the database. The schema relies on Postgres-specific
features — pgvector, declarative partitioning, ENUM types, JSONB, triggers — and
mocked tests would mask migration bugs.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """A real Postgres with pgvector preinstalled.

    Uses pgvector/pgvector:pg16 so CREATE EXTENSION vector succeeds. TimescaleDB
    is intentionally absent: the migration treats it as best-effort, so the
    default test path exercises the no-Timescale branch.
    """
    container = PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="agenttape",
        password="agenttape",
        dbname="agenttape_test",
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


def _sync_url(c: PostgresContainer) -> str:
    """Convert testcontainers' default psycopg2 URL to plain psycopg2 (Alembic)."""
    return c.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)


def _async_url(c: PostgresContainer) -> str:
    return _sync_url(c).replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture(scope="session")
def alembic_config(postgres_container: PostgresContainer) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _sync_url(postgres_container))
    # Ensure migrations/env.py can import our package.
    sys.path.insert(0, str(API_DIR / "src"))
    return cfg


@pytest.fixture(scope="session")
def migrated_db(
    postgres_container: PostgresContainer, alembic_config: Config
) -> Iterator[PostgresContainer]:
    """Run migrations once per session, then yield the container."""
    os.environ["DATABASE_URL"] = _sync_url(postgres_container)
    command.upgrade(alembic_config, "head")
    yield postgres_container


@pytest_asyncio.fixture
async def engine(migrated_db: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(_async_url(migrated_db), pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _reset_data(engine: AsyncEngine) -> AsyncIterator[None]:
    """Truncate all data between tests but keep the schema intact."""
    yield
    async with engine.begin() as conn:
        # Order matters less with CASCADE, but we restart identities for cleanliness.
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "events, rebalances, index_snapshots, index_members, indexes, "
            "scores, benchmark_results, benchmarks, signals, "
            "agent_tags, tags, discovery_candidates, agents "
            "RESTART IDENTITY CASCADE"
        )
