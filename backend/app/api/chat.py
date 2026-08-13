"""
Chat API — Student ↔ Teacher live doubt system + Phase 9 AI Chatbot.

Student endpoints (require role=student):
  GET  /lectures/{lecture_id}/chat        → student's own AI chat thread (all messages)
  POST /lectures/{lecture_id}/chat        → student asks AI chatbot; returns AI reply pair
  GET  /lectures/{lecture_id}/doubts      → student's doubt thread (student+teacher only, no AI)
  POST /lectures/{lecture_id}/doubts      → student posts a doubt to teacher (no AI)

Teacher endpoints (require role=teacher):
  GET  /teacher/lectures/{lecture_id}/chat                       → all student doubt threads (no AI msgs)
  POST /teacher/lectures/{lecture_id}/chat/{thread_id}           → teacher posts a reply
  GET  /teacher/lectures/{lecture_id}/chat/analytics             → doubt analytics
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database.database import get_db
from app.database.models import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatThreadRead,
    TeacherThreadRead,
    AIChatResponse,
    LectureDoubtAnalytics,
)
import app.services.chat_service as chat_svc
import app.services.chatbot_service as chatbot_svc

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


@router.get(
    "/{lecture_id}/doubts",
    response_model=ChatThreadRead,
    tags=["chat", "student"],
)
async def student_get_doubts(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Return the student's doubt thread for this lecture, containing only
    student and teacher messages (AI messages are excluded).
    """
    return await chat_svc.get_student_doubt_thread(db, lecture_id, current_user.id)


@router.post(
    "/{lecture_id}/doubts",
    response_model=ChatMessageRead,
    status_code=201,
    tags=["chat", "student"],
)
async def student_post_doubt(
    lecture_id: str,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Post a student doubt to the teacher (no AI involvement).
    Appends a student message to the thread and returns it.
    """
    return await chat_svc.post_student_message(
        db, lecture_id, current_user.id, payload.content
    )


@router.post(
    "/{lecture_id}/chat",
    response_model=AIChatResponse,
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
    Post a student question to the AI chatbot for this lecture.

    The AI:
    1. Retrieves relevant lecture context (transcript, notes, topics, events).
    2. Classifies the question against the lecture's known topics.
    3. Generates a grounded answer using Groq LLM.
    4. Persists both the student question and the AI reply.
    5. Returns both messages.

    The chatbot is scoped strictly to this lecture — it will not use
    information from other lectures.
    """
    student_msg, ai_msg = await chatbot_svc.ask_ai(
        db, lecture_id, current_user.id, payload.content
    )
    return AIChatResponse(student_message=student_msg, ai_message=ai_msg)


# ---------------------------------------------------------------------------
# Teacher endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/teacher/lectures/{lecture_id}/chat/analytics",
    response_model=LectureDoubtAnalytics,
    tags=["chat", "teacher"],
)
async def teacher_get_analytics(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return aggregated student doubt analytics for a lecture owned by this teacher.

    Analytics include:
    - Total students who asked doubts
    - Total questions
    - Per-topic breakdown: unique student count + percentage + question count

    Student identities are NOT exposed — only anonymized counts.
    Percentages are based on unique students per topic, not message count.
    """
    return await chat_svc.get_doubt_analytics(db, lecture_id, current_user.id)


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
