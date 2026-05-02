"""Shared fixtures.

Two independent scopes here:

- A real Postgres (pgvector pg16) brought up by testcontainers, with the
  apps/api Alembic migrations applied. Used by promoter tests so we
  exercise the actual schema, not a hand-rolled approximation.
- VCR cassettes per scout so HTTP calls are recorded on first run and
  replayed thereafter. ``record_mode='new_episodes'`` means tests still
  pass after we add a new query without re-recording the whole cassette.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

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


# ---------------------------------------------------------------- VCR


@pytest.fixture
def vcr_config() -> dict:
    # Strip auth headers so we don't bake real tokens into cassettes.
    return {
        "filter_headers": [
            "authorization",
            "x-api-key",
            "anthropic-api-key",
        ],
        "record_mode": "new_episodes",
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
    }


@pytest.fixture
def vcr_cassette_dir(request) -> str:
    return str(Path(request.module.__file__).parent / "cassettes")


# --------------------------------------------------------- real-postgres


@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer

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


def _sync_url(container) -> str:
    return container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


def _async_url(container) -> str:
    return _sync_url(container).replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


@pytest.fixture(scope="session")
def migrated_db(postgres_container):
    """Apply apps/api Alembic migrations against the test container."""
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
            "TRUNCATE TABLE "
            "events, agent_tags, tags, discovery_candidates, agents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def settings_with_db(migrated_db, monkeypatch):
    """Point Settings at the test container without a network call."""
    monkeypatch.setenv("DATABASE_URL", _async_url(migrated_db))
    # Make sure we don't hit Anthropic/Voyage during promoter tests.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    # Reset the lazy global engine in discovery.db so it picks up the new URL.
    import discovery.db as ddb

    ddb._engine = None
    ddb._factory = None
    from discovery.config import get_settings

    return get_settings()
