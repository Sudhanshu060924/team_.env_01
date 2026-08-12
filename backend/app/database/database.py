from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


# Engine is created lazily on first use so tests can patch settings before import.
_engine = None
_session_factory = None


def _coerce_async_url(url: str) -> str:
    """
    Ensure the DATABASE_URL uses an async-compatible driver scheme.

    Neon / Supabase / Heroku often give you:
      postgresql://...  or  postgres://...
    SQLAlchemy asyncio requires:
      postgresql+psycopg://...   (psycopg v3, already in requirements.txt)
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    # already has a driver specifier (e.g. postgresql+psycopg://...) — leave as-is
    return url


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        url = settings.DATABASE_URL
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to backend/.env"
            )
        url = _coerce_async_url(url)
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, factory = _get_engine()
    async with factory() as session:
        yield session


async def create_tables() -> None:
    """Create all tables on startup if they don't exist."""
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
