"""
Authentication tests.

All tests mock the database and auth service so no real Neon connection
is required. Session state is tested against the in-process session store.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.auth import UserRead
from app.database.models import User
import app.services.auth_service as auth_svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    role: str = "student",
    name: str = "Test User",
    email: str = "test@example.com",
) -> User:
    u = User()
    u.id = str(uuid.uuid4())
    u.name = name
    u.email = email
    u.password_hash = auth_svc.hash_password("password123")
    u.role = role
    u.created_at = datetime.now(timezone.utc)
    return u


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/signup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_signup():
    user = _make_user(role="student")
    with patch("app.api.auth.auth_svc.signup", new_callable=AsyncMock, return_value=_user_read(user)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/signup",
                json={"name": "Test User", "email": "test@example.com", "password": "password123", "role": "student"},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "student"
    assert "password_hash" not in body
    assert "session_token" in resp.cookies


@pytest.mark.asyncio
async def test_teacher_signup():
    user = _make_user(role="teacher", name="Dr. Smith", email="teacher@school.com")
    with patch("app.api.auth.auth_svc.signup", new_callable=AsyncMock, return_value=_user_read(user)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/signup",
                json={"name": "Dr. Smith", "email": "teacher@school.com", "password": "secure123", "role": "teacher"},
            )
    assert resp.status_code == 201
    assert resp.json()["role"] == "teacher"


@pytest.mark.asyncio
async def test_duplicate_email():
    from fastapi import HTTPException
    exc = HTTPException(status_code=409, detail="Email already registered")
    with patch("app.api.auth.auth_svc.signup", new_callable=AsyncMock, side_effect=exc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/signup",
                json={"name": "Alice", "email": "dup@example.com", "password": "password123", "role": "student"},
            )
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_role():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={"name": "X", "email": "x@example.com", "password": "password123", "role": "admin"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_password_too_short():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={"name": "X", "email": "x@example.com", "password": "short", "role": "student"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_email_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={"name": "X", "email": "not-an-email", "password": "password123", "role": "student"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_login():
    user = _make_user(role="student")
    with patch("app.api.auth.auth_svc.login", new_callable=AsyncMock, return_value=user):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/login",
                json={"email": user.email, "password": "password123"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email
    assert body["role"] == "student"
    assert "password_hash" not in body
    assert "session_token" in resp.cookies


@pytest.mark.asyncio
async def test_wrong_password():
    from fastapi import HTTPException
    exc = HTTPException(status_code=401, detail="Invalid email or password")
    with patch("app.api.auth.auth_svc.login", new_callable=AsyncMock, side_effect=exc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/login",
                json={"email": "user@example.com", "password": "wrongpass"},
            )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_current_user():
    user = _make_user(role="teacher")
    token = auth_svc.create_session(user.id)

    with patch("app.api.deps.get_user_id_from_session", return_value=user.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=user):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/api/auth/me")

    auth_svc.delete_session(token)
    assert resp.status_code == 200
    assert resp.json()["role"] == "teacher"
    assert "password_hash" not in resp.json()


@pytest.mark.asyncio
async def test_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout():
    user = _make_user()
    token = auth_svc.create_session(user.id)
    assert auth_svc.get_user_id_from_session(token) == user.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("session_token", token)
        resp = await client.post("/api/auth/logout")

    assert resp.status_code == 204
    assert auth_svc.get_user_id_from_session(token) is None


# ---------------------------------------------------------------------------
# Role enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthorized_no_cookie():
    """A protected endpoint without a cookie returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_require_role_student():
    """require_role('student') passes for a student user."""
    from app.api.deps import require_role
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    test_app = FastAPI()
    student = _make_user(role="student")
    token = auth_svc.create_session(student.id)

    @test_app.get("/student-only")
    async def _ep(user=__import__("fastapi", fromlist=["Depends"]).Depends(require_role("student"))):
        return {"ok": True}

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student), \
         patch("app.database.database.get_db"):
        from app.database.database import get_db as _get_db

        async def _fake_db():
            yield None

        test_app.dependency_overrides[_get_db] = _fake_db

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/student-only")

    auth_svc.delete_session(token)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_require_role_teacher_rejects_student():
    """require_role('teacher') returns 403 for a student."""
    from app.api.deps import require_role
    from fastapi import FastAPI

    test_app = FastAPI()
    student = _make_user(role="student")
    token = auth_svc.create_session(student.id)

    @test_app.get("/teacher-only")
    async def _ep(user=__import__("fastapi", fromlist=["Depends"]).Depends(require_role("teacher"))):
        return {"ok": True}

    with patch("app.api.deps.get_user_id_from_session", return_value=student.id), \
         patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=student):
        from app.database.database import get_db as _get_db

        async def _fake_db():
            yield None

        test_app.dependency_overrides[_get_db] = _fake_db

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            client.cookies.set("session_token", token)
            resp = await client.get("/teacher-only")

    auth_svc.delete_session(token)
    assert resp.status_code == 403
