from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ingestion.config import get_settings


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


async def reset_globals() -> None:
    """Drop cached engine/factory — used by tests after monkeypatching env vars."""
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None
