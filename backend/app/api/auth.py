"""
Authentication API routes.

POST /api/auth/signup  — create account
POST /api/auth/login   — exchange credentials for session cookie
POST /api/auth/logout  — delete session cookie
GET  /api/auth/me      — return current user
"""

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database.database import get_db
from app.database.models import User
from app.schemas.auth import LoginRequest, SignupRequest, UserRead
import app.services.auth_service as auth_svc


router = APIRouter()


_COOKIE_NAME = "session_token"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _set_session_cookie(response: Response, user_id: str) -> str:
    token = auth_svc.create_session(user_id)

    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )

    return token


@router.post("/signup", response_model=UserRead, status_code=201)
async def signup(
    payload: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account and start a session."""

    user_read = await auth_svc.signup(db, payload)

    _set_session_cookie(
        response,
        user_read.id,
    )

    return user_read


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Validate credentials and issue a session cookie."""

    user = await auth_svc.login(
        db,
        payload.email,
        payload.password,
    )

    token = auth_svc.create_session(user.id)

    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )

    return auth_svc._to_read(user)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None),
):
    """Delete the session cookie."""

    if session_token:
        auth_svc.delete_session(session_token)

    response.delete_cookie(
        key=_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user."""

    return auth_svc._to_read(current_user)