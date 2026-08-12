"""
Shared pytest fixtures.

Patches database initialisation so tests don't require a real Neon connection.
Patches FFmpeg check so tests don't require FFmpeg to be installed.
"""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.integrations.groq_limiter import reset_semaphore


@pytest.fixture(autouse=True)
def _reset_groq_semaphore():
    """Reset the Groq concurrency semaphore before every test."""
    reset_semaphore()
    yield
    reset_semaphore()


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    """
    Prevent any real database access during tests:
    - create_tables() is a no-op (kept in case any helper calls it directly)
    - get_db() yields None (services are mocked per-test)
    """
    with patch("app.database.database.create_tables", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
def _patch_ffmpeg():
    """
    Prevent the lifespan FFmpeg check from raising during tests.
    Individual audio preprocessor tests mock at a lower level.
    """
    with patch(
        "app.services.audio_preprocessor.check_ffmpeg",
        return_value="/usr/bin/ffmpeg",
    ):
        yield


@pytest.fixture(autouse=True)
def _override_get_db():
    """Override the FastAPI get_db dependency so routes never touch a real DB."""
    from app.database.database import get_db
    from app.main import app

    async def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    yield
    app.dependency_overrides.clear()
