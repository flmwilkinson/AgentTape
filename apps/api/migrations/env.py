from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from agenttape_api.db.base import Base
from agenttape_api.db import models  # noqa: F401  -- register models on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow DATABASE_URL env var to override sqlalchemy.url in alembic.ini.
db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not db_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Provide it via env or alembic.ini sqlalchemy.url."
    )
# Alembic uses sync drivers; coerce to psycopg (v3) regardless of input form.
# Accept asyncpg URLs (used by the app) and bare ``postgresql://`` URLs.
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Skip auto-generated DROPs for objects we manage by raw SQL.

    These are created explicitly in 0001_initial and live outside SQLAlchemy's
    metadata view: the current_scores view, signals partitions, the partition
    helper function, and the Timescale extension hint.
    """
    if type_ == "table" and name and name.startswith("signals_p"):
        return False
    if type_ == "table" and name == "current_scores":
        return False
    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
