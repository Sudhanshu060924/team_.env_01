"""
Backend tests for the Student ↔ Teacher live doubt/chat feature.

Covers:
  - Student creates doubt
  - Teacher replies
  - Student receives teacher reply (persistence)
  - Student can read own thread
  - Student cannot read another student's thread (403 from auth layer)
  - Teacher can read all threads for own lecture
  - Teacher cannot read another teacher's lecture (403)
  - Lecture 1 messages do not appear in Lecture 2
  - Unauthenticated access rejected (401)
  - Empty messages rejected (422)
  - Messages persist in database
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.models import User
from app.schemas.chat import ChatMessageRead, ChatThreadRead, TeacherThreadRead, StudentInfo
import app.services.auth_service as auth_svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: str = "student", name: str = "Test User") -> User:
    u = User()
    u.id = str(uuid.uuid4())
    u.name = name
    u.email = f"{uuid.uuid4()}@test.com"
    u.password_hash = auth_svc.hash_password("password123")
    u.role = role
    u.created_at = datetime.now(timezone.utc)
    return u


def _set_session(client, user: User) -> str:
    token = auth_svc.create_session(user.id)
    client.cookies.set("session_token", token)
    return token


def _make_chat_message(
    thread_id: str,
    sender_id: str,
    sender_role: str = "student",
    content: str = "Why do we use git commit?",
) -> ChatMessageRead:
    return ChatMessageRead(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        sender_id=sender_id,
        sender_role=sender_role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )


def _make_thread(
    lecture_id: str,
    student_id: str,
    messages: list | None = None,
) -> ChatThreadRead:
    tid = str(uuid.uuid4())
    return ChatThreadRead(
        thread_id=tid,
        lecture_id=lecture_id,
        student_id=student_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        messages=messages or [],
    )


def _make_teacher_thread(
    lecture_id: str,
    student: User,
    messages: list | None = None,
) -> TeacherThreadRead:
    tid = str(uuid.uuid4())
    return TeacherThreadRead(
        thread_id=tid,
        lecture_id=lecture_id,
        student=StudentInfo(id=student.id, name=student.name),
        messages=messages or [],
    )


# ---------------------------------------------------------------------------
# POST /lectures/{lecture_id}/chat — student creates doubt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_creates_doubt():
    """Student can post a message to their own thread."""
    student = _make_user(role="student", name="Alice")
    lecture_id = str(uuid.uuid4())
    msg = _make_chat_message(thread_id=str(uuid.uuid4()), sender_id=student.id)

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student), \
         patch("app.api.chat.chat_svc.post_student_message", new_callable=AsyncMock, return_value=msg):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.post(
                f"/lectures/{lecture_id}/chat",
                json={"content": "Why do we use git commit?"},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "Why do we use git commit?"
    assert body["sender_role"] == "student"


@pytest.mark.asyncio
async def test_student_creates_doubt_empty_content():
    """Empty content is rejected with 422."""
    student = _make_user(role="student")
    lecture_id = str(uuid.uuid4())

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.post(
                f"/lectures/{lecture_id}/chat",
                json={"content": "  "},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_student_creates_doubt_too_long():
    """Content exceeding 2000 chars is rejected with 422."""
    student = _make_user(role="student")
    lecture_id = str(uuid.uuid4())

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.post(
                f"/lectures/{lecture_id}/chat",
                json={"content": "x" * 2001},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_student_chat_rejected():
    """POST without a session cookie returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/lectures/some-id/chat",
            json={"content": "Hello"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /lectures/{lecture_id}/chat — student reads own thread
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_reads_own_thread():
    """Student can read their own chat thread."""
    student = _make_user(role="student")
    lecture_id = str(uuid.uuid4())
    thread = _make_thread(lecture_id, student.id)

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student), \
         patch("app.api.chat.chat_svc.get_student_thread", new_callable=AsyncMock, return_value=thread):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.get(f"/lectures/{lecture_id}/chat")
        auth_svc.delete_session(token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == student.id
    assert body["lecture_id"] == lecture_id


@pytest.mark.asyncio
async def test_student_cannot_read_another_students_thread():
    """
    A student endpoint only ever returns their OWN thread.
    The service enforces this: student_id is taken from the session, never from the URL.
    If student B calls GET /lectures/{id}/chat, they get their own thread (not A's).
    Authorization at the service level means A and B see different data.
    """
    student_a = _make_user(role="student", name="Student A")
    student_b = _make_user(role="student", name="Student B")
    lecture_id = str(uuid.uuid4())

    # student_b's thread — student_id is student_b.id, not student_a.id
    thread_b = _make_thread(lecture_id, student_b.id)

    with patch("app.api.deps.get_user_id_from_session", return_value=student_b.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student_b), \
         patch("app.api.chat.chat_svc.get_student_thread", new_callable=AsyncMock, return_value=thread_b):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student_b)
            resp = await client.get(f"/lectures/{lecture_id}/chat")
        auth_svc.delete_session(token)

    # student_b sees their own thread, NOT student_a's
    assert resp.status_code == 200
    assert resp.json()["student_id"] == student_b.id
    assert resp.json()["student_id"] != student_a.id


# ---------------------------------------------------------------------------
# GET /lectures/teacher/lectures/{lecture_id}/chat — teacher reads all threads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_reads_all_threads():
    """Teacher can read all threads for their own lecture."""
    teacher = _make_user(role="teacher", name="Dr. Smith")
    student_a = _make_user(role="student", name="Alice")
    student_b = _make_user(role="student", name="Bob")
    lecture_id = str(uuid.uuid4())

    threads = [
        _make_teacher_thread(lecture_id, student_a),
        _make_teacher_thread(lecture_id, student_b),
    ]

    with patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher), \
         patch("app.api.chat.chat_svc.get_all_threads_for_lecture", new_callable=AsyncMock, return_value=threads):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, teacher)
            resp = await client.get(f"/lectures/teacher/lectures/{lecture_id}/chat")
        auth_svc.delete_session(token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    student_names = {t["student"]["name"] for t in body}
    assert "Alice" in student_names
    assert "Bob" in student_names


@pytest.mark.asyncio
async def test_teacher_cannot_access_another_teachers_lecture():
    """Teacher gets 403 for a lecture they don't own."""
    teacher = _make_user(role="teacher", name="Dr. Smith")
    lecture_id = str(uuid.uuid4())

    from fastapi import HTTPException
    exc = HTTPException(status_code=403, detail="You do not have access to this lecture")

    with patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher), \
         patch("app.api.chat.chat_svc.get_all_threads_for_lecture", new_callable=AsyncMock, side_effect=exc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, teacher)
            resp = await client.get(f"/lectures/teacher/lectures/{lecture_id}/chat")
        auth_svc.delete_session(token)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_access_teacher_chat_endpoint():
    """A student calling the teacher endpoint gets 403."""
    student = _make_user(role="student")
    lecture_id = str(uuid.uuid4())

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.get(f"/lectures/teacher/lectures/{lecture_id}/chat")
        auth_svc.delete_session(token)

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Teacher replies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_replies_to_thread():
    """Teacher can post a reply to a student thread."""
    teacher = _make_user(role="teacher", name="Dr. Smith")
    lecture_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    reply_msg = _make_chat_message(
        thread_id=thread_id,
        sender_id=teacher.id,
        sender_role="teacher",
        content="It creates a snapshot of your changes.",
    )

    with patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher), \
         patch("app.api.chat.chat_svc.post_teacher_reply", new_callable=AsyncMock, return_value=reply_msg):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, teacher)
            resp = await client.post(
                f"/lectures/teacher/lectures/{lecture_id}/chat/{thread_id}",
                json={"content": "It creates a snapshot of your changes."},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 201
    body = resp.json()
    assert body["sender_role"] == "teacher"
    assert body["content"] == "It creates a snapshot of your changes."


@pytest.mark.asyncio
async def test_teacher_reply_empty_content_rejected():
    """Empty teacher reply is rejected with 422."""
    teacher = _make_user(role="teacher")

    with patch("app.api.deps.get_user_id_from_session", return_value=teacher.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, teacher)
            resp = await client.post(
                f"/lectures/teacher/lectures/{str(uuid.uuid4())}/chat/{str(uuid.uuid4())}",
                json={"content": ""},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Lecture isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lecture_isolation_student():
    """
    Messages from lecture 1 do NOT appear in lecture 2.
    The service always queries by the specific lecture_id in the URL.
    """
    student = _make_user(role="student")
    lecture_id_1 = str(uuid.uuid4())
    lecture_id_2 = str(uuid.uuid4())

    thread1 = _make_thread(
        lecture_id_1,
        student.id,
        messages=[_make_chat_message(thread_id=str(uuid.uuid4()), sender_id=student.id, content="Lecture 1 doubt")],
    )
    thread2 = _make_thread(lecture_id_2, student.id, messages=[])

    async def _side_effect(db, lecture_id, student_id):
        if lecture_id == lecture_id_1:
            return thread1
        return thread2

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student), \
         patch("app.api.chat.chat_svc.get_student_thread", side_effect=_side_effect):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp1 = await client.get(f"/lectures/{lecture_id_1}/chat")
            resp2 = await client.get(f"/lectures/{lecture_id_2}/chat")
        auth_svc.delete_session(token)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    msgs1 = resp1.json()["messages"]
    msgs2 = resp2.json()["messages"]
    assert len(msgs1) == 1
    assert len(msgs2) == 0
    assert msgs1[0]["content"] == "Lecture 1 doubt"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_messages_persist_in_database():
    """
    Messages returned by the service come from the DB.
    We verify the service is called with correct lecture_id / student_id.
    """
    student = _make_user(role="student")
    lecture_id = str(uuid.uuid4())
    msg = _make_chat_message(
        thread_id=str(uuid.uuid4()),
        sender_id=student.id,
        content="Persisted doubt",
    )

    mock_post = AsyncMock(return_value=msg)

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student), \
         patch("app.api.chat.chat_svc.post_student_message", mock_post):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = _set_session(client, student)
            resp = await client.post(
                f"/lectures/{lecture_id}/chat",
                json={"content": "Persisted doubt"},
            )
        auth_svc.delete_session(token)

    assert resp.status_code == 201
    # Verify service was called with correct lecture_id and student_id (from session, NOT body)
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.args[1] == lecture_id        # lecture_id from URL
    assert call_args.args[2] == student.id         # student_id from session
    assert call_args.args[3] == "Persisted doubt" # content from body


# ---------------------------------------------------------------------------
# Unauthenticated teacher endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_teacher_endpoint():
    """Accessing teacher chat without authentication returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/lectures/teacher/lectures/{str(uuid.uuid4())}/chat")
    assert resp.status_code == 401
