from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _async_url(url: str) -> str:
    """Coerce a Postgres URL to the asyncpg-compatible form.

    Pins the dialect to ``+asyncpg`` and strips libpq-only query
    params (``sslmode``, ``channel_binding``) that asyncpg rejects.
    Neon enforces TLS at the transport layer regardless.
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parts = urlsplit(url)
    drop = {"sslmode", "channel_binding"}
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in drop]
    return urlunsplit(parts._replace(query=urlencode(qs)))


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return _async_url(url)


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def engine():  # type: ignore[no-untyped-def]
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_database_url(), pool_pre_ping=True)
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
