"""
Tests for lecture ownership (teacher_id), authenticated endpoints,
and access control.

Tasks covered:
  1. Existing lectures can still load (teacher_id=NULL).
  2. teacher_id can be NULL for legacy lectures.
  3. Teacher creates lecture → teacher_id set to current user.
  4. Teacher cannot supply teacher_id from the frontend.
  5. Teacher lecture list only returns own lectures.
  6. Student lecture list works (completed only).
  7. Student cannot access a non-completed lecture via /student/lectures/{id}.
  8. Existing lecture history endpoint still works.
  9. Unauthenticated start still creates lecture with teacher_id=NULL.
 10. Existing test helpers/schemas are unaffected.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.lecture import LectureRead
from app.database.models import User
import app.services.auth_service as auth_svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: str = "teacher", user_id: str | None = None) -> User:
    u = User()
    u.id = user_id or str(uuid.uuid4())
    u.name = "Test User"
    u.email = f"{u.id}@example.com"
    u.password_hash = auth_svc.hash_password("password123")
    u.role = role
    u.created_at = datetime.now(timezone.utc)
    return u


def _make_lecture(
    title: str = "Physics 101",
    status: str = "completed",
    teacher_id: str | None = None,
) -> LectureRead:
    return LectureRead(
        lecture_id=str(uuid.uuid4()),
        title=title,
        video_name="lecture.mp4",
        status=status,
        teacher_id=teacher_id,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
    )


def _auth_cookies(user: User):
    token = auth_svc.create_session(user.id)
    return {"session_token": token}, token


# ---------------------------------------------------------------------------
# 1 + 2: Legacy lectures with teacher_id=NULL still load
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_lecture_null_teacher_id():
    """Existing lectures with teacher_id=NULL must be readable."""
    lecture = _make_lecture(teacher_id=None)
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["lecture_id"] == lecture.lecture_id
    assert body["teacher_id"] is None


@pytest.mark.asyncio
async def test_list_lectures_includes_null_teacher_id():
    """GET /lectures returns lectures that have teacher_id=NULL."""
    lectures = [_make_lecture(teacher_id=None), _make_lecture(teacher_id=str(uuid.uuid4()))]
    with patch("app.api.lectures.lecture_svc.list_lectures", new_callable=AsyncMock, return_value=lectures):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/lectures")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["teacher_id"] is None


# ---------------------------------------------------------------------------
# 3: Teacher creates lecture — teacher_id set from auth, not from payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_creates_lecture_sets_teacher_id():
    """POST /lectures/start with auth → teacher_id = current_user.id."""
    teacher = _make_user(role="teacher")
    expected_lecture = _make_lecture(status="live", teacher_id=teacher.id)
    cookies, token = _auth_cookies(teacher)

    created_lecture_capture = {}

    async def fake_create(db, payload, teacher_id=None):
        created_lecture_capture["teacher_id"] = teacher_id
        return expected_lecture

    with patch("app.api.lectures.lecture_svc.create_lecture", side_effect=fake_create), \
         patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.post(
                "/lectures/start",
                json={"title": "Physics 101", "video_name": "lecture.mp4"},
            )

    auth_svc.delete_session(token)
    assert resp.status_code == 201
    assert created_lecture_capture["teacher_id"] == teacher.id


# ---------------------------------------------------------------------------
# 4: Frontend cannot override teacher_id — LectureCreate has no teacher_id field
# ---------------------------------------------------------------------------

def test_lecture_create_schema_has_no_teacher_id():
    """LectureCreate must not accept teacher_id (prevents ownership spoofing)."""
    from app.schemas.lecture import LectureCreate
    import inspect
    fields = LectureCreate.model_fields
    assert "teacher_id" not in fields, "LectureCreate must NOT expose teacher_id"


# ---------------------------------------------------------------------------
# 5: Teacher lecture list returns only own lectures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_list_lectures_own_only():
    teacher = _make_user(role="teacher")
    own_lecture = _make_lecture(status="live", teacher_id=teacher.id)
    cookies, token = _auth_cookies(teacher)

    with patch("app.api.lectures.lecture_svc.list_teacher_lectures", new_callable=AsyncMock, return_value=[own_lecture]), \
         patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/lectures/teacher/lectures")

    auth_svc.delete_session(token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["teacher_id"] == teacher.id


@pytest.mark.asyncio
async def test_teacher_list_lectures_requires_teacher_role():
    """A student cannot access the teacher lecture list."""
    student = _make_user(role="student")
    cookies, token = _auth_cookies(student)

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/lectures/teacher/lectures")

    auth_svc.delete_session(token)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6: Student lecture list (completed only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_list_lectures_returns_completed():
    student = _make_user(role="student")
    completed = _make_lecture(status="completed")
    cookies, token = _auth_cookies(student)

    with patch("app.api.lectures.lecture_svc.list_student_lectures", new_callable=AsyncMock, return_value=[completed]), \
         patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/lectures/student/lectures")

    auth_svc.delete_session(token)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_student_list_lectures_requires_student_role():
    """A teacher cannot access the student lecture list."""
    teacher = _make_user(role="teacher")
    cookies, token = _auth_cookies(teacher)

    with patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/lectures/student/lectures")

    auth_svc.delete_session(token)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7: Student cannot access a non-completed (live) lecture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_cannot_access_live_lecture():
    """GET /lectures/student/lectures/{id} returns 404 for a live lecture."""
    student = _make_user(role="student")
    cookies, token = _auth_cookies(student)

    with patch("app.api.lectures.lecture_svc.get_lecture_for_student", new_callable=AsyncMock, return_value=None), \
         patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get(f"/lectures/student/lectures/{uuid.uuid4()}")

    auth_svc.delete_session(token)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_student_get_lecture_returns_completed():
    """GET /lectures/student/lectures/{id} returns the lecture when completed."""
    student = _make_user(role="student")
    lecture = _make_lecture(status="completed")
    cookies, token = _auth_cookies(student)

    with patch("app.api.lectures.lecture_svc.get_lecture_for_student", new_callable=AsyncMock, return_value=lecture), \
         patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get(f"/lectures/student/lectures/{lecture.lecture_id}")

    auth_svc.delete_session(token)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# 8: Legacy /lectures/{id} still works (history access via unrestricted endpoint)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legacy_get_lecture_still_works():
    lecture = _make_lecture(status="completed", teacher_id=None)
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}")
    assert resp.status_code == 200
    assert resp.json()["lecture_id"] == lecture.lecture_id


# ---------------------------------------------------------------------------
# 9: Unauthenticated start creates lecture with teacher_id=NULL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_start_lecture_teacher_id_null():
    """POST /lectures/start without cookie → teacher_id=None passed to service."""
    captured = {}

    async def fake_create(db, payload, teacher_id=None):
        captured["teacher_id"] = teacher_id
        return _make_lecture(status="live", teacher_id=None)

    with patch("app.api.lectures.lecture_svc.create_lecture", side_effect=fake_create):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/lectures/start",
                json={"title": "Anon Lecture", "video_name": "vid.mp4"},
            )

    assert resp.status_code == 201
    assert captured["teacher_id"] is None


# ---------------------------------------------------------------------------
# 10: lecture_service helpers work correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_student_lectures_service():
    """list_student_lectures only includes completed lectures."""
    from app.services.lecture_service import list_student_lectures
    from unittest.mock import MagicMock

    completed = _make_lecture(status="completed")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        # Build a bare Lecture ORM-like object
        type("Lecture", (), {
            "id": completed.lecture_id,
            "title": completed.title,
            "video_name": completed.video_name,
            "status": "completed",
            "teacher_id": None,
            "created_at": completed.created_at,
            "completed_at": completed.completed_at,
            "video_url": None,
            "cloudinary_public_id": None,
        })()
    ]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_student_lectures(mock_db)
    assert len(result) == 1
    assert result[0].status == "completed"


@pytest.mark.asyncio
async def test_list_teacher_lectures_service():
    """list_teacher_lectures filters by teacher_id."""
    from app.services.lecture_service import list_teacher_lectures
    from unittest.mock import MagicMock

    teacher_id = str(uuid.uuid4())
    lecture = _make_lecture(status="live", teacher_id=teacher_id)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        type("Lecture", (), {
            "id": lecture.lecture_id,
            "title": lecture.title,
            "video_name": lecture.video_name,
            "status": "live",
            "teacher_id": teacher_id,
            "created_at": lecture.created_at,
            "completed_at": None,
            "video_url": None,
            "cloudinary_public_id": None,
        })()
    ]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_teacher_lectures(mock_db, teacher_id)
    assert len(result) == 1
    assert result[0].teacher_id == teacher_id
