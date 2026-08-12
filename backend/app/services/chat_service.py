"""
Chat service — Student ↔ Teacher live doubt system.

Authorization rules (all enforced here, never trusted from the frontend):
  - Students may only read/write their own thread for a given lecture.
  - Teachers may read/write all threads for lectures they own.
  - Lecture isolation: every query always filters by lecture_id.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ChatThread, ChatMessage, Lecture, User
from app.schemas.chat import (
    ChatMessageRead,
    ChatThreadRead,
    TeacherThreadRead,
    StudentInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _message_to_read(msg: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=msg.id,
        thread_id=msg.thread_id,
        sender_id=msg.sender_id,
        sender_role=msg.sender_role,
        content=msg.content,
        created_at=msg.created_at,
    )


def _thread_to_read(thread: ChatThread) -> ChatThreadRead:
    return ChatThreadRead(
        thread_id=thread.id,
        lecture_id=thread.lecture_id,
        student_id=thread.student_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=[_message_to_read(m) for m in thread.messages],
    )


def _thread_to_teacher_read(thread: ChatThread) -> TeacherThreadRead:
    student = thread.student
    return TeacherThreadRead(
        thread_id=thread.id,
        lecture_id=thread.lecture_id,
        student=StudentInfo(id=student.id, name=student.name),
        messages=[_message_to_read(m) for m in thread.messages],
    )


async def _get_lecture(db: AsyncSession, lecture_id: str) -> Lecture:
    """Return the lecture or raise 404."""
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


async def _require_teacher_owns_lecture(
    db: AsyncSession,
    lecture_id: str,
    teacher_id: str,
) -> Lecture:
    """Raise 403 if the authenticated teacher does not own this lecture."""
    lecture = await _get_lecture(db, lecture_id)
    if lecture.teacher_id != teacher_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this lecture",
        )
    return lecture


async def _get_or_create_student_thread(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
) -> ChatThread:
    """Return an existing thread or create a new one (upsert by unique constraint)."""
    stmt = (
        select(ChatThread)
        .where(ChatThread.lecture_id == lecture_id, ChatThread.student_id == student_id)
        .options(selectinload(ChatThread.messages), selectinload(ChatThread.student))
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()
    if thread is None:
        thread = ChatThread(lecture_id=lecture_id, student_id=student_id)
        db.add(thread)
        await db.flush()  # populate thread.id
        await db.refresh(thread)
        # Reload with relationships
        result2 = await db.execute(stmt)
        thread = result2.scalar_one()
    return thread


# ---------------------------------------------------------------------------
# Student operations
# ---------------------------------------------------------------------------

async def get_student_thread(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
) -> ChatThreadRead:
    """Return the student's thread for this lecture (creates it if needed)."""
    await _get_lecture(db, lecture_id)
    thread = await _get_or_create_student_thread(db, lecture_id, student_id)
    return _thread_to_read(thread)


async def post_student_message(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
    content: str,
) -> ChatMessageRead:
    """
    Append a student message to their thread for this lecture.
    Creates the thread if it doesn't exist yet.
    """
    await _get_lecture(db, lecture_id)
    thread = await _get_or_create_student_thread(db, lecture_id, student_id)

    msg = ChatMessage(
        thread_id=thread.id,
        sender_id=student_id,
        sender_role="student",
        content=content,
    )
    db.add(msg)

    # Touch updated_at on the thread
    thread.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(msg)
    return _message_to_read(msg)


# ---------------------------------------------------------------------------
# Teacher operations
# ---------------------------------------------------------------------------

async def get_all_threads_for_lecture(
    db: AsyncSession,
    lecture_id: str,
    teacher_id: str,
) -> List[TeacherThreadRead]:
    """
    Return all student threads for a lecture owned by this teacher.
    Raises 403 if the teacher does not own the lecture.
    """
    await _require_teacher_owns_lecture(db, lecture_id, teacher_id)

    stmt = (
        select(ChatThread)
        .where(ChatThread.lecture_id == lecture_id)
        .options(
            selectinload(ChatThread.messages),
            selectinload(ChatThread.student),
        )
        .order_by(ChatThread.created_at)
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()
    return [_thread_to_teacher_read(t) for t in threads]


async def post_teacher_reply(
    db: AsyncSession,
    lecture_id: str,
    thread_id: str,
    teacher_id: str,
    content: str,
) -> ChatMessageRead:
    """
    Append a teacher reply to a specific thread.
    Verifies the teacher owns the lecture that the thread belongs to.
    """
    # Verify thread exists and belongs to this lecture
    stmt = (
        select(ChatThread)
        .where(ChatThread.id == thread_id, ChatThread.lecture_id == lecture_id)
        .options(selectinload(ChatThread.student))
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Verify teacher owns the lecture
    await _require_teacher_owns_lecture(db, lecture_id, teacher_id)

    msg = ChatMessage(
        thread_id=thread_id,
        sender_id=teacher_id,
        sender_role="teacher",
        content=content,
    )
    db.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return _message_to_read(msg)
