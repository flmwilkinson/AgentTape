"""Test fixtures: real Postgres + a fake Redis client.

Same shape as apps/discovery's conftest. The Redis dependency is
deliberately mocked here — we want to assert what *would* be
published without spinning up a real Redis just for these tests.
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


def _sync_url(c) -> str:
    return c.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


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
            "TRUNCATE TABLE events, signals, agent_tags, tags, "
            "discovery_candidates, agents RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def settings_with_db(migrated_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _async_url(migrated_db))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)

    import ingestion.db as idb

    idb._engine = None
    idb._factory = None

    from ingestion.config import get_settings

    return get_settings()


class FakeRedis:
    """Records ``publish`` calls so tests can assert on them."""

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
