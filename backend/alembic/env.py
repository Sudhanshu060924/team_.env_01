"""
Alembic env.py — VidyaRoom backend (async SQLAlchemy + psycopg v3)

Key design decisions
--------------------
* DATABASE_URL is read from the environment / .env file via the project's
  own `get_settings()`.  No credentials are ever hardcoded here.
* The project already uses an async engine (postgresql+psycopg://).
  Alembic's standard synchronous `run_migrations_online` cannot call async
  code directly; we use `asyncio.run()` with an AsyncConnection so Alembic
  drives the migration inside a real async context.
* `target_metadata` is set to `Base.metadata` after importing every model
  module, ensuring autogenerate sees the full current schema.
* `migrations_applied` (the legacy ad-hoc SQL runner's table) is excluded
  from autogenerate so Alembic never tries to drop it.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

# psycopg v3 requires SelectorEventLoop on Windows.
# This must be set before any async call, including asyncio.run() at the bottom.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Make sure `backend/` (this file's parent) is on sys.path so that
# `from app.xxx import ...` works when alembic is invoked from backend/.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Project imports — order matters.
# 1. Import Base first.
# 2. Import every model module so their classes register on Base.metadata
#    before autogenerate inspects it.
# ---------------------------------------------------------------------------
from app.database.database import Base          # noqa: E402  — must come after sys.path tweak
import app.database.models  # noqa: F401, E402  — registers User, Lecture, LectureEventModel, NoteModel, ChatThread, ChatMessage

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Honour the logging configuration in alembic.ini (if present).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata — used by autogenerate
# ---------------------------------------------------------------------------
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL at runtime from project settings.
# Never read from alembic.ini (sqlalchemy.url is intentionally blank there).
# ---------------------------------------------------------------------------
def _get_database_url() -> str:
    """
    Return the async-compatible DATABASE_URL.

    Precedence:
      1. ALEMBIC_DATABASE_URL env var (override for CI / special cases)
      2. DATABASE_URL from project Settings (reads .env)
    """
    url = os.environ.get("ALEMBIC_DATABASE_URL", "")
    if not url:
        from app.config import get_settings
        url = get_settings().DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set.  "
            "Set it in backend/.env or as the ALEMBIC_DATABASE_URL env var."
        )
    # Ensure async driver prefix (same logic as app/database/database.py)
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


# ---------------------------------------------------------------------------
# Tables that exist in the database but are NOT managed by Alembic.
# autogenerate will ignore them — they will not be dropped or modified.
# ---------------------------------------------------------------------------
_EXCLUDE_TABLES = {
    "migrations_applied",  # legacy ad-hoc SQL migration tracker — keep as-is
}


def _include_object(obj, name, type_, reflected, compare_to):
    """Filter function for autogenerate — skip unmanaged tables."""
    if type_ == "table" and name in _EXCLUDE_TABLES:
        return False
    return True


# ---------------------------------------------------------------------------
# Offline mode — generate SQL without connecting to the database
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout / file)."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connect to Neon and run migrations
# ---------------------------------------------------------------------------
def _run_migrations_sync(connection) -> None:
    """Inner sync function called inside an async connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        # include_schemas=False,  # set True if you use non-public schemas
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    We create a *temporary* engine here only for the migration run.
    This engine is disposed immediately afterwards — it does not interfere
    with the application's own engine created in app/database/database.py.
    """
    url = _get_database_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,   # No pooling for migration runs
        echo=False,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations_sync)
    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
