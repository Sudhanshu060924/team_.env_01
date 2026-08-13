"""
Feedback / Analytics service — Teacher Dashboard.

Aggregates data from:
  - Lecture table              (total lectures, titles)
  - ChatThread + ChatMessage   (student ↔ AI questions and student ↔ teacher doubts)
  - LectureRating              (1–5 star ratings + written feedback)

All aggregation is done in the database; raw messages are never returned to the
caller except as anonymized question text in FeedbackTopicDetail.

Three streams remain strictly separate:
  "ai_chat"  — student ↔ AI chatbot
  "doubt"    — student ↔ teacher (NULL rows treated as "doubt")
  ratings    — lecture_ratings table (completely independent)
"""
from typing import List, Optional

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChatMessage, ChatThread, Lecture
from app.schemas.feedback import FeedbackOverview, FeedbackTopic, FeedbackTopicDetail
import app.services.rating_service as rating_svc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _lecture_ids_for_teacher(db: AsyncSession, teacher_id: str) -> List[str]:
    result = await db.execute(
        select(Lecture.id).where(Lecture.teacher_id == teacher_id)
    )
    return list(result.scalars().all())


async def _thread_ids_for_lectures(db: AsyncSession, lecture_ids: List[str]) -> List[str]:
    if not lecture_ids:
        return []
    result = await db.execute(
        select(ChatThread.id).where(ChatThread.lecture_id.in_(lecture_ids))
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def get_overview(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: Optional[str] = None,
) -> FeedbackOverview:
    """
    Return aggregated overview stats (engagement + ratings combined).

    If lecture_id is given, stats are scoped to that single lecture
    (teacher ownership is assumed to have been verified by the API layer).
    """
    # ── Lectures ──────────────────────────────────────────────────────────
    if lecture_id:
        lecture_ids = [lecture_id]
        total_lectures = 1
    else:
        lecture_ids = await _lecture_ids_for_teacher(db, teacher_id)
        total_lectures = len(lecture_ids)

    if not lecture_ids:
        return FeedbackOverview(
            total_lectures=0,
            total_students=0,
            total_questions=0,
            total_doubts=0,
            total_ai_questions=0,
            most_asked_topic=None,
        )

    # ── Thread IDs for these lectures ─────────────────────────────────────
    thread_ids = await _thread_ids_for_lectures(db, lecture_ids)

    # ── Total unique students (anyone with a thread for these lectures) ───
    if thread_ids:
        students_stmt = (
            select(func.count(distinct(ChatThread.student_id)))
            .where(ChatThread.lecture_id.in_(lecture_ids))
        )
        total_students: int = (await db.execute(students_stmt)).scalar_one() or 0
    else:
        total_students = 0

    # ── AI-chat questions (student messages with message_type="ai_chat") ─
    if thread_ids:
        ai_q_stmt = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.thread_id.in_(thread_ids),
                ChatMessage.sender_role == "student",
                ChatMessage.message_type == "ai_chat",
            )
        )
        total_ai_questions: int = (await db.execute(ai_q_stmt)).scalar_one() or 0
    else:
        total_ai_questions = 0

    # ── Doubt messages from students (message_type="doubt" or NULL) ───────
    if thread_ids:
        doubt_stmt = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.thread_id.in_(thread_ids),
                ChatMessage.sender_role == "student",
                ChatMessage.message_type.in_(["doubt"]) | ChatMessage.message_type.is_(None),
            )
        )
        total_doubts: int = (await db.execute(doubt_stmt)).scalar_one() or 0
    else:
        total_doubts = 0

    # ── Most asked topic (from AI replies that have detected_topic) ────────
    most_asked_topic: Optional[str] = None
    if thread_ids:
        topic_stmt = (
            select(ChatMessage.detected_topic, func.count(ChatMessage.id).label("cnt"))
            .where(
                ChatMessage.thread_id.in_(thread_ids),
                ChatMessage.sender_role == "ai",
                ChatMessage.message_type == "ai_chat",
                ChatMessage.detected_topic.isnot(None),
            )
            .group_by(ChatMessage.detected_topic)
            .order_by(func.count(ChatMessage.id).desc())
            .limit(1)
        )
        topic_result = await db.execute(topic_stmt)
        topic_row = topic_result.first()
        most_asked_topic = topic_row[0] if topic_row else None

    # ── Rating aggregates ─────────────────────────────────────────────────
    rating_analytics = await rating_svc.get_rating_analytics(db, lecture_ids)
    most_rated, lowest_rated = await rating_svc.get_lecture_rating_summary(db, lecture_ids)

    return FeedbackOverview(
        total_lectures=total_lectures,
        total_students=total_students,
        total_questions=total_ai_questions,
        total_doubts=total_doubts,
        total_ai_questions=total_ai_questions,
        most_asked_topic=most_asked_topic,
        avg_rating=rating_analytics.avg_rating,
        total_ratings=rating_analytics.total_ratings,
        most_rated_lecture=most_rated,
        lowest_rated_lecture=lowest_rated,
    )


async def get_topics(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: Optional[str] = None,
) -> List[FeedbackTopic]:
    """
    Return per-topic breakdown sorted by question_count descending.

    Percentages are calculated as (topic_count / total_ai_questions) * 100.
    If lecture_id is given, stats are scoped to that lecture.
    """
    if lecture_id:
        lecture_ids = [lecture_id]
    else:
        lecture_ids = await _lecture_ids_for_teacher(db, teacher_id)

    if not lecture_ids:
        return []

    thread_ids = await _thread_ids_for_lectures(db, lecture_ids)
    if not thread_ids:
        return []

    # Fetch lecture id → title mapping (needed for the "all lectures" view)
    lec_title_result = await db.execute(
        select(Lecture.id, Lecture.title).where(Lecture.id.in_(lecture_ids))
    )
    lecture_title_map: dict[str, str] = {row[0]: row[1] for row in lec_title_result.all()}

    # Per-topic AI message counts, with lecture_id
    topic_stmt = (
        select(
            ChatMessage.detected_topic,
            ChatThread.lecture_id,
            func.count(ChatMessage.id).label("cnt"),
        )
        .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
        .where(
            ChatMessage.thread_id.in_(thread_ids),
            ChatMessage.sender_role == "ai",
            ChatMessage.message_type == "ai_chat",
            ChatMessage.detected_topic.isnot(None),
        )
        .group_by(ChatMessage.detected_topic, ChatThread.lecture_id)
        .order_by(func.count(ChatMessage.id).desc())
    )
    topic_result = await db.execute(topic_stmt)
    rows = topic_result.all()  # (detected_topic, lecture_id, count)

    if not rows:
        return []

    total = sum(r[2] for r in rows)

    topics: List[FeedbackTopic] = []
    for detected_topic, lec_id, count in rows:
        topics.append(
            FeedbackTopic(
                topic=detected_topic,
                question_count=count,
                percentage=round(count / total * 100, 1) if total > 0 else 0.0,
                lecture_id=lec_id if not lecture_id else None,
                lecture_title=lecture_title_map.get(lec_id) if not lecture_id else None,
            )
        )

    return topics


async def get_lecture_overview(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: str,
) -> FeedbackOverview:
    """Convenience wrapper: overview for a single lecture."""
    return await get_overview(db, teacher_id, lecture_id=lecture_id)


async def get_lecture_topics(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: str,
) -> List[FeedbackTopic]:
    """Convenience wrapper: topics for a single lecture."""
    return await get_topics(db, teacher_id, lecture_id=lecture_id)
