"""
Auth dependencies — reusable FastAPI Depends() helpers.

  get_current_user()          — extract + validate session cookie, return User (raises 401 if missing)
  get_optional_current_user() — same but returns None instead of raising 401
  require_role(role)          — factory: returns a dep that asserts the user role
"""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.models import User
from app.services.auth_service import get_user_id_from_session, get_user_by_id


async def get_current_user(
    session_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated User or raise 401."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = get_user_id_from_session(session_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_current_user(
    session_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated User, or None if no valid session cookie."""
    if not session_token:
        return None

    user_id = get_user_id_from_session(session_token)
    if not user_id:
        return None

    return await get_user_by_id(db, user_id)


def require_role(role: str):
    """
    Factory that returns a FastAPI dependency enforcing the given role.

    Usage::

        @router.post("/teacher-only")
        async def endpoint(user = Depends(require_role("teacher"))):
            ...
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{role}' role; you are '{user.role}'",
            )
        return user

    return _check
