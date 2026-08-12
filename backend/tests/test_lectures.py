"""
Phase 2 tests — Lecture CRUD.

These tests use an in-memory SQLite database so they don't require a real
Neon connection. The async SQLAlchemy engine is overridden via dependency
injection.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.lecture import LectureRead
from app.schemas.events import LectureEvent
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lecture(title="Test Lecture", video_name="demo.mp4") -> LectureRead:
    return LectureRead(
        lecture_id=str(uuid.uuid4()),
        title=title,
        video_name=video_name,
        status="live",
        created_at=datetime.now(timezone.utc),
    )


def _make_event(lecture_id: str) -> LectureEvent:
    return LectureEvent(
        event_id=str(uuid.uuid4()),
        lecture_id=lecture_id,
        timestamp=10.0,
        type="speech",
        source="whisper",
        content="Hello world",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_lecture():
    lecture = _make_lecture()
    with patch("app.api.lectures.lecture_svc.create_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/lectures/start",
                json={"title": "Test Lecture", "video_name": "demo.mp4"},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Test Lecture"
    assert body["status"] == "live"
    assert "lecture_id" in body


@pytest.mark.asyncio
async def test_get_lecture_found():
    lecture = _make_lecture()
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}")
    assert resp.status_code == 200
    assert resp.json()["lecture_id"] == lecture.lecture_id


@pytest.mark.asyncio
async def test_get_lecture_not_found():
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/lectures/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_complete_lecture():
    lecture = _make_lecture()
    completed = lecture.model_copy(update={"status": "completed"})
    with patch("app.api.lectures.lecture_svc.complete_lecture", new_callable=AsyncMock, return_value=completed):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/lectures/{lecture.lecture_id}/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_get_events():
    lecture = _make_lecture()
    events = [_make_event(lecture.lecture_id)]
    with patch("app.api.lectures.event_svc.get_events", new_callable=AsyncMock, return_value=events):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}/events")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "speech"


@pytest.mark.asyncio
async def test_get_notes_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/lectures/any-id/notes")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_ask_question_stub():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/lectures/any-id/questions",
            json={"question": "Why is binary search O(log n)?"},
        )
    assert resp.status_code == 200
    assert "answer" in resp.json()
