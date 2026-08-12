"""
Phase 3 tests — WebSocket connection and message protocol.

Uses Starlette's built-in synchronous TestClient for WebSocket testing,
which requires no extra dependencies.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """Sync test client with lifespan disabled (DB already patched by conftest)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_ws_connect_receives_greeting(client):
    """Client connects and immediately receives a 'connected' message."""
    with client.websocket_connect("/ws/lectures/lec-test-1") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["lecture_id"] == "lec-test-1"


def test_ws_ping_pong(client):
    """Client sends ping, server replies pong."""
    with client.websocket_connect("/ws/lectures/lec-ping") as ws:
        ws.receive_json()  # consume greeting
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_ws_lecture_completed(client):
    """
    lecture_completed message triggers a broadcast back to the client.
    DB calls inside the background task are patched at source.
    """
    async def _noop_db():
        yield None

    with (
        patch("app.database.database.get_db", side_effect=_noop_db),
        patch("app.services.event_service.save_event", new_callable=AsyncMock),
        patch("app.services.lecture_service.complete_lecture", new_callable=AsyncMock),
    ):
        with client.websocket_connect("/ws/lectures/lec-complete") as ws:
            ws.receive_json()  # greeting
            ws.send_json({
                "type": "lecture_completed",
                "lecture_id": "lec-complete",
                "timestamp": 3600.0,
            })
            msg = ws.receive_json()
            assert msg["type"] == "lecture_completed"
