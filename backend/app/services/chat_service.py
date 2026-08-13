"""
Chat service — Student ↔ Teacher live doubt system.

Authorization rules (all enforced here, never trusted from the frontend):
  - Students may only read/write their own thread for a given lecture.
  - Teachers may read/write all threads for lectures they own.
  - Lecture isolation: every query always filters by lecture_id.

message_type values in ChatMessage:
  "ai_chat" — created by the AI chatbot flow (student question + AI reply)
  "doubt"   — created by the student ↔ teacher doubt flow
  NULL      — pre-migration rows; treated as "doubt"
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ChatThread, ChatMessage, Lecture, User
from app.schemas.chat import (
    ChatMessageRead,
    ChatThreadRead,
    TeacherThreadRead,
    StudentInfo,
    LectureDoubtAnalytics,
    TopicAnalytic,
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
        detected_topic=msg.detected_topic,
        ai_answer=msg.ai_answer,
    )


def _is_doubt(msg: ChatMessage) -> bool:
    """True for student ↔ teacher messages.  NULL message_type is legacy doubt data."""
    return msg.message_type in ("doubt", None)


def _is_ai_chat(msg: ChatMessage) -> bool:
    return msg.message_type == "ai_chat"


def _thread_to_read(thread: ChatThread, ai_chat_only: bool = False) -> ChatThreadRead:
    if ai_chat_only:
        messages = [_message_to_read(m) for m in thread.messages if _is_ai_chat(m)]
    else:
        messages = [_message_to_read(m) for m in thread.messages]
    return ChatThreadRead(
        thread_id=thread.id,
        lecture_id=thread.lecture_id,
        student_id=thread.student_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=messages,
    )


def _thread_to_teacher_read(thread: ChatThread) -> TeacherThreadRead:
    """Teacher view shows only student ↔ teacher doubt messages (no AI)."""
    student = thread.student
    return TeacherThreadRead(
        thread_id=thread.id,
        lecture_id=thread.lecture_id,
        student=StudentInfo(id=student.id, name=student.name),
        messages=[
            _message_to_read(m)
            for m in thread.messages
            if _is_doubt(m) and m.sender_role in ("student", "teacher")
        ],
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
    """
    Return the student's AI-chat messages for this lecture (Chat tab).
    Only messages with message_type="ai_chat" are included.
    Creates the thread if it doesn't exist yet.
    """
    await _get_lecture(db, lecture_id)
    thread = await _get_or_create_student_thread(db, lecture_id, student_id)
    return _thread_to_read(thread, ai_chat_only=True)


async def get_student_doubt_thread(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
) -> ChatThreadRead:
    """
    Return the student's doubt messages for this lecture (Doubts tab).
    Only student ↔ teacher messages (message_type="doubt" or NULL) are returned.
    Creates the thread if it doesn't exist yet.
    """
    await _get_lecture(db, lecture_id)
    thread = await _get_or_create_student_thread(db, lecture_id, student_id)
    doubt_only = ChatThreadRead(
        thread_id=thread.id,
        lecture_id=thread.lecture_id,
        student_id=thread.student_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=[
            _message_to_read(m)
            for m in thread.messages
            if _is_doubt(m) and m.sender_role in ("student", "teacher")
        ],
    )
    return doubt_only


async def post_student_message(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
    content: str,
) -> ChatMessageRead:
    """
    Append a student doubt message to their thread for this lecture (Doubts tab).
    Tagged as message_type="doubt" so it is never shown in the Chat tab.
    Creates the thread if it doesn't exist yet.
    """
    await _get_lecture(db, lecture_id)
    thread = await _get_or_create_student_thread(db, lecture_id, student_id)

    msg = ChatMessage(
        thread_id=thread.id,
        sender_id=student_id,
        sender_role="student",
        content=content,
        message_type="doubt",
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
    Tagged as message_type="doubt" so it appears in the student's Doubts tab.
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
        message_type="doubt",
    )
    db.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return _message_to_read(msg)


# ---------------------------------------------------------------------------
# Phase 9 — Teacher analytics
# ---------------------------------------------------------------------------

async def get_doubt_analytics(
    db: AsyncSession,
    lecture_id: str,
    teacher_id: str,
) -> LectureDoubtAnalytics:
    """
    Return aggregated doubt analytics for a lecture owned by this teacher.

    - Verifies teacher owns the lecture.
    - topic percentages are based on UNIQUE students per topic, not message count.
    - Student identities are NOT returned — only anonymized counts.
    """
    await _require_teacher_owns_lecture(db, lecture_id, teacher_id)

    # Count total students who have access to any student-visible lecture.
    # Since we don't have an enrollment table, we use the count of distinct
    # students who have ever opened a chat thread for this lecture as the
    # denominator. If no threads exist we use the total thread count across
    # all lectures as a fallback, but the safest approach is:
    # total_students = distinct students who have a thread for this lecture
    # (which represents engagement, not enrollment).
    # For a true enrollment count we'd need an enrollment table.

    # Students with at least one thread for this lecture
    threads_stmt = (
        select(ChatThread.student_id)
        .where(ChatThread.lecture_id == lecture_id)
        .distinct()
    )
    threads_result = await db.execute(threads_stmt)
    all_student_ids: list[str] = list(threads_result.scalars().all())
    total_students_in_threads = len(all_student_ids)

    # Students who asked at least one AI-chat question
    student_questions_stmt = (
        select(ChatThread.student_id)
        .join(ChatMessage, ChatMessage.thread_id == ChatThread.id)
        .where(
            ChatThread.lecture_id == lecture_id,
            ChatMessage.sender_role == "student",
            ChatMessage.message_type == "ai_chat",
        )
        .distinct()
    )
    sq_result = await db.execute(student_questions_stmt)
    students_with_doubts_ids: list[str] = list(sq_result.scalars().all())
    students_with_doubts = len(students_with_doubts_ids)

    # Total AI-chat questions from students (denominator for topic percentages)
    total_q_stmt = (
        select(func.count(ChatMessage.id))
        .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
        .where(
            ChatThread.lecture_id == lecture_id,
            ChatMessage.sender_role == "student",
            ChatMessage.message_type == "ai_chat",
        )
    )
    total_q_result = await db.execute(total_q_stmt)
    total_questions: int = total_q_result.scalar_one() or 0

    # Per-topic analytics:
    # For each AI reply that has a detected_topic, count:
    #   - unique students who asked about that topic
    #   - number of student questions paired with that topic
    # We join AI messages back to the thread to get student_id.

    # Fetch all AI messages with a detected_topic for this lecture.
    # Filter to message_type="ai_chat" to exclude any hypothetical
    # future AI messages that might appear in the doubt channel.
    ai_msgs_stmt = (
        select(ChatMessage.detected_topic, ChatThread.student_id)
        .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
        .where(
            ChatThread.lecture_id == lecture_id,
            ChatMessage.sender_role == "ai",
            ChatMessage.message_type == "ai_chat",
            ChatMessage.detected_topic.isnot(None),
        )
    )
    ai_msgs_result = await db.execute(ai_msgs_stmt)
    ai_rows = ai_msgs_result.all()  # (detected_topic, student_id)

    # Aggregate per topic
    from collections import defaultdict
    topic_students: dict[str, set[str]] = defaultdict(set)
    topic_q_count: dict[str, int] = defaultdict(int)
    for detected_topic, student_id in ai_rows:
        if detected_topic:
            topic_students[detected_topic].add(student_id)
            topic_q_count[detected_topic] += 1

    # Denominator for percentage = students_with_doubts (students who asked ≥1 question)
    # If 0 students asked, percentages are all 0
    denom = students_with_doubts if students_with_doubts > 0 else 1

    topics_list: list[TopicAnalytic] = []
    for topic_name, student_set in sorted(
        topic_students.items(), key=lambda x: len(x[1]), reverse=True
    ):
        sc = len(student_set)
        topics_list.append(
            TopicAnalytic(
                topic=topic_name,
                students_count=sc,
                percentage=round(sc / denom * 100, 1),
                question_count=topic_q_count[topic_name],
            )
        )

    most_asked = topics_list[0].topic if topics_list else None

    # For total_students, use the larger of thread count vs students_with_doubts
    # (there may be students who opened the chat but never asked anything)
    total_students = max(total_students_in_threads, students_with_doubts)

    return LectureDoubtAnalytics(
        lecture_id=lecture_id,
        total_students=total_students,
        students_with_doubts=students_with_doubts,
        total_questions=total_questions,
        most_asked_topic=most_asked,
        topics=topics_list,
    )
