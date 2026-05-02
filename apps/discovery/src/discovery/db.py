from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from discovery.config import get_settings


def _async_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _async_url(get_settings().database_url), pool_pre_ping=True
        )
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(engine(), expire_on_commit=False)
    return _factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
