"""
Shared pytest fixtures.

Patches database initialisation so tests don't require a real Neon connection.
"""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    """
    Prevent any real database access during tests:
    - create_tables() is a no-op
    - get_db() yields None (services are mocked per-test)
    """
    # Patch create_tables used in lifespan
    with patch("app.database.database.create_tables", new_callable=AsyncMock):
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
