"""
Chat API — Student ↔ Teacher live doubt system.

Student endpoints (require role=student):
  GET  /lectures/{lecture_id}/chat        → student's own thread + messages
  POST /lectures/{lecture_id}/chat        → student posts a new doubt/message

Teacher endpoints (require role=teacher):
  GET  /teacher/lectures/{lecture_id}/chat              → all threads for the lecture
  POST /teacher/lectures/{lecture_id}/chat/{thread_id}  → teacher posts a reply
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database.database import get_db
from app.database.models import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatThreadRead,
    TeacherThreadRead,
)
import app.services.chat_service as chat_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{lecture_id}/chat",
    response_model=ChatThreadRead,
    tags=["chat", "student"],
)
async def student_get_chat(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Return the authenticated student's own chat thread for this lecture.
    Creates an empty thread if this is the first visit.
    """
    return await chat_svc.get_student_thread(db, lecture_id, current_user.id)


@router.post(
    "/{lecture_id}/chat",
    response_model=ChatMessageRead,
    status_code=201,
    tags=["chat", "student"],
)
async def student_post_message(
    lecture_id: str,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Post a new doubt/message as the authenticated student.
    The backend determines student_id and lecture_id from the session.
    """
    return await chat_svc.post_student_message(
        db, lecture_id, current_user.id, payload.content
    )


# ---------------------------------------------------------------------------
# Teacher endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/teacher/lectures/{lecture_id}/chat",
    response_model=List[TeacherThreadRead],
    tags=["chat", "teacher"],
)
async def teacher_get_chat(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return all student doubt threads for a lecture owned by this teacher.
    Raises 403 if the teacher does not own the lecture.
    """
    return await chat_svc.get_all_threads_for_lecture(db, lecture_id, current_user.id)


@router.post(
    "/teacher/lectures/{lecture_id}/chat/{thread_id}",
    response_model=ChatMessageRead,
    status_code=201,
    tags=["chat", "teacher"],
)
async def teacher_post_reply(
    lecture_id: str,
    thread_id: str,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Post a reply to a specific student thread.
    Verifies the teacher owns the lecture the thread belongs to.
    """
    return await chat_svc.post_teacher_reply(
        db, lecture_id, thread_id, current_user.id, payload.content
    )
