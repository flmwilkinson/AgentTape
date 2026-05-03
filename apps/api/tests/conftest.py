"""Top-level test fixtures shared by both ``tests/db/`` (schema tests) and
``tests/test_api_routes.py`` (route tests).

The DB stack is real: pgvector/pgvector:pg16 via testcontainers, with the
Alembic migrations applied once per test session. Tests get clean state
through the ``_reset_data`` autouse fixture below.
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

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
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
    return c.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)


def _async_url(c: PostgresContainer) -> str:
    return _sync_url(c).replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture(scope="session")
def alembic_config(postgres_container: PostgresContainer) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _sync_url(postgres_container))
    sys.path.insert(0, str(API_DIR / "src"))
    return cfg


@pytest.fixture(scope="session")
def migrated_db(
    postgres_container: PostgresContainer, alembic_config: Config
) -> Iterator[PostgresContainer]:
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
    yield
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "events, rebalances, index_snapshots, index_members, indexes, "
            "scores, benchmark_results, benchmarks, signals, "
            "agent_tags, tags, discovery_candidates, agents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def settings_with_db(migrated_db: PostgresContainer, monkeypatch):
    """Point the API's lazy session factory at the test container."""
    monkeypatch.setenv("DATABASE_URL", _async_url(migrated_db))
    # Reset the lazy globals so a new engine picks up the env var.
    from agenttape_api.db import session as db_session  # type: ignore

    db_session._engine = None
    db_session._session_factory = None
    return None
