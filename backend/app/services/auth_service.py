"""
Authentication service.

Password hashing uses bcrypt directly (bcrypt>=4.0 — already a transitive dep).
Sessions are stored server-side as a UUID token in an HTTP-only cookie.
A simple in-process dict backs the session store for MVP;
for multi-process deployments swap _sessions for Redis or a DB table.
"""
import uuid
from typing import Optional

import bcrypt as _bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.schemas.auth import UserRead, SignupRequest


# ---------------------------------------------------------------------------
# Password hashing — bcrypt (>=4.0)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# In-process session store  {token: user_id}
# ---------------------------------------------------------------------------

_sessions: dict[str, str] = {}


def create_session(user_id: str) -> str:
    token = str(uuid.uuid4())
    _sessions[token] = user_id
    return token


def get_user_id_from_session(token: str) -> Optional[str]:
    return _sessions.get(token)


def delete_session(token: str) -> None:
    _sessions.pop(token, None)


def _clear_all_sessions() -> None:
    """Test helper — wipe all sessions."""
    _sessions.clear()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

ALLOWED_ROLES = {"student", "teacher"}


def _to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


async def signup(db: AsyncSession, payload: SignupRequest) -> UserRead:
    from fastapi import HTTPException

    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {sorted(ALLOWED_ROLES)}")

    # Email uniqueness check
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _to_read(user)


async def login(db: AsyncSession, email: str, password: str) -> User:
    from fastapi import HTTPException

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
