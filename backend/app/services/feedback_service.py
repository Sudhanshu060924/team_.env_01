"""
Feedback / Analytics service — Teacher Dashboard.

Aggregates data from:
  - Lecture table              (total lectures, titles)
  - ChatThread + ChatMessage   (student ↔ AI questions and student ↔ teacher doubts)
  - LectureRating              (1–5 star ratings + written feedback)
  - PlaybackAnalytics          (video engagement — separate from all the above)

All aggregation is done in the database; raw messages are never returned to the
caller except as anonymized question text in FeedbackTopicDetail.

Four streams remain strictly separate:
  "ai_chat"  — student ↔ AI chatbot
  "doubt"    — student ↔ teacher (NULL rows treated as "doubt")
  ratings    — lecture_ratings table (completely independent)
  playback   — playback_analytics table (completely independent)
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChatMessage, ChatThread, Lecture, PlaybackAnalytics
from app.schemas.feedback import (
    FeedbackOverview,
    FeedbackTopic,
    FeedbackTopicDetail,
    ProblemSolvingStats,
    TeacherPerformanceScore,
)
import app.services.rating_service as rating_svc
import app.services.playback_service as playback_svc
from app.services.performance_config import WEIGHTS, MIN_RATINGS, MIN_DOUBTS, MIN_PLAYBACK_ROWS


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
# Problem Solving (Student ↔ Teacher doubts only — no AI chat)
# ---------------------------------------------------------------------------

async def get_problem_solving(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: Optional[str] = None,
) -> ProblemSolvingStats:
    """
    Compute doubt response metrics for a teacher.
    ONLY counts student ↔ teacher doubt messages (message_type="doubt" or NULL).
    AI chatbot messages are excluded.
    """
    if lecture_id:
        lecture_ids = [lecture_id]
    else:
        lecture_ids = await _lecture_ids_for_teacher(db, teacher_id)

    if not lecture_ids:
        return ProblemSolvingStats()

    thread_ids = await _thread_ids_for_lectures(db, lecture_ids)
    if not thread_ids:
        return ProblemSolvingStats()

    # Total student doubt messages
    doubt_stmt = (
        select(func.count(ChatMessage.id))
        .where(
            ChatMessage.thread_id.in_(thread_ids),
            ChatMessage.sender_role == "student",
            ChatMessage.message_type.in_(["doubt"]) | ChatMessage.message_type.is_(None),
        )
    )
    total_doubts: int = (await db.execute(doubt_stmt)).scalar_one() or 0

    # Answered: threads where the teacher has replied at least once
    answered_stmt = (
        select(func.count(distinct(ChatMessage.thread_id)))
        .where(
            ChatMessage.thread_id.in_(thread_ids),
            ChatMessage.sender_role == "teacher",
            ChatMessage.message_type.in_(["doubt"]) | ChatMessage.message_type.is_(None),
        )
    )
    answered_threads: int = (await db.execute(answered_stmt)).scalar_one() or 0

    # Total threads with at least one doubt
    total_threads_stmt = (
        select(func.count(distinct(ChatThread.id)))
        .where(
            ChatThread.id.in_(thread_ids),
        )
    )
    total_threads: int = (await db.execute(total_threads_stmt)).scalar_one() or 0

    response_rate = round(answered_threads / total_threads * 100, 1) if total_threads > 0 else 0.0
    resolved_pct = response_rate  # same metric for now

    return ProblemSolvingStats(
        total_doubts=total_doubts,
        answered_doubts=answered_threads,
        response_rate_pct=response_rate,
        avg_response_time_minutes=None,   # would require timestamps diff; future work
        resolved_pct=resolved_pct,
    )


# ---------------------------------------------------------------------------
# Teacher Performance Score
# ---------------------------------------------------------------------------

async def get_teacher_score(
    db: AsyncSession,
    teacher_id: str,
) -> TeacherPerformanceScore:
    """
    Calculate the composite teacher performance score (0–5).

    Uses WEIGHTS from performance_config.py.

    IMPORTANT: fewer AI questions do NOT automatically mean a better teacher.
    The AI dependency signal combines AI usage with completion, replays, and
    rewinds to distinguish curious engaged students from confused students.
    """
    lecture_ids = await _lecture_ids_for_teacher(db, teacher_id)
    if not lecture_ids:
        return TeacherPerformanceScore()

    # ── Rating sub-score ──────────────────────────────────────────────────────
    rating_analytics = await rating_svc.get_rating_analytics(db, lecture_ids)
    rating_sub: Optional[float] = None
    if rating_analytics.total_ratings >= MIN_RATINGS and rating_analytics.avg_rating is not None:
        rating_sub = float(rating_analytics.avg_rating)   # already 1–5

    # ── Problem-solving sub-score ─────────────────────────────────────────────
    ps = await get_problem_solving(db, teacher_id)
    ps_sub: Optional[float] = None
    if ps.total_doubts >= MIN_DOUBTS:
        # response_rate_pct is 0–100; convert to 0–5
        ps_sub = round(ps.response_rate_pct / 100 * 5, 2)

    # ── Playback-based sub-scores ──────────────────────────────────────────────
    engagement = await playback_svc.get_lecture_engagement(db, lecture_ids)
    engagement_sub: Optional[float] = None
    completion_sub: Optional[float] = None
    if engagement.total_views >= MIN_PLAYBACK_ROWS:
        # Student engagement: weighted average of completion + active interactions
        # More pauses/replays/rewinds relative to total views → higher engagement
        interaction_rate = min(
            1.0,
            (engagement.pause_count + engagement.replay_count + engagement.rewind_count)
            / max(1, engagement.total_views * 5),
        )
        # Engagement = 70% completion + 30% interaction rate
        engagement_sub = round(
            (engagement.avg_completion_pct / 100 * 0.7 + interaction_rate * 0.3) * 5,
            2,
        )
        # Lecture completion sub-score
        completion_sub = round(engagement.avg_completion_pct / 100 * 5, 2)

    # ── AI dependency signal ──────────────────────────────────────────────────
    ai_sub: Optional[float] = None
    thread_ids = await _thread_ids_for_lectures(db, lecture_ids)
    if thread_ids:
        ai_stmt = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.thread_id.in_(thread_ids),
                ChatMessage.sender_role == "student",
                ChatMessage.message_type == "ai_chat",
            )
        )
        total_ai: int = (await db.execute(ai_stmt)).scalar_one() or 0

        student_count_stmt = (
            select(func.count(distinct(ChatThread.student_id)))
            .where(ChatThread.lecture_id.in_(lecture_ids))
        )
        student_count: int = (await db.execute(student_count_stmt)).scalar_one() or 0

        if student_count > 0:
            ai_per_student = total_ai / student_count
            # High AI + high completion + low rewinds → curious students (good)
            # High AI + low completion + high rewinds → struggling students
            completion_factor = (engagement.avg_completion_pct / 100) if engagement.total_views > 0 else 0.5
            rewind_penalty = min(
                1.0,
                (engagement.rewind_count + engagement.replay_count) / max(1, engagement.total_views * 3),
            ) if engagement.total_views > 0 else 0.0

            # Normalize AI questions: 0–5 per student is normal
            ai_norm = min(1.0, ai_per_student / 10.0)

            # Positive signal: high AI + high completion
            positive = ai_norm * completion_factor

            # Negative signal: high AI + high rewinds (students struggling)
            negative = ai_norm * rewind_penalty * 0.5

            raw = (positive - negative + 0.5)  # bias toward middle
            ai_sub = round(min(5.0, max(0.0, raw * 5)), 2)

    # ── Composite score ───────────────────────────────────────────────────────
    weighted_sum = 0.0
    active_weight = 0.0

    sub_scores = [
        ("overall_rating",     rating_sub,     WEIGHTS["overall_rating"]),
        ("problem_solving",    ps_sub,         WEIGHTS["problem_solving"]),
        ("student_engagement", engagement_sub, WEIGHTS["student_engagement"]),
        ("lecture_completion", completion_sub, WEIGHTS["lecture_completion"]),
        ("ai_dependency",      ai_sub,         WEIGHTS["ai_dependency"]),
    ]

    for _, score, weight in sub_scores:
        if score is not None:
            weighted_sum += score * weight
            active_weight += weight

    overall: Optional[float] = None
    if active_weight > 0:
        # Normalize so missing dimensions don't push score to zero
        overall = round(weighted_sum / active_weight * 5 / 5, 2)
        # Clamp to [0, 5]
        overall = round(min(5.0, max(0.0, overall)), 2)

    return TeacherPerformanceScore(
        overall=overall,
        overall_rating=rating_sub,
        problem_solving=ps_sub,
        student_engagement=engagement_sub,
        lecture_completion=completion_sub,
        ai_dependency=ai_sub,
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def get_overview(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: Optional[str] = None,
) -> FeedbackOverview:
    """
    Return aggregated overview stats (engagement + ratings + teacher score combined).

    If lecture_id is given, stats are scoped to that single lecture
    (teacher ownership is assumed to have been verified by the API layer).
    Teacher performance score is always teacher-wide (not per-lecture).
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

    # ── Teacher performance score (always teacher-wide) ───────────────────
    teacher_score = await get_teacher_score(db, teacher_id)

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
        teacher_score=teacher_score,
    )


async def get_topics(
    db: AsyncSession,
    teacher_id: str,
    lecture_id: Optional[str] = None,
) -> List[FeedbackTopic]:
    """
    Return per-topic breakdown sorted by question_count descending.
    Extended with playback data (replays, rewinds, pauses) per topic
    based on which lecture the topic belongs to.
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

    # Fetch lecture id → title mapping
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

    # Build playback aggregates per lecture_id for the engagement extension
    pb_stats: dict[str, dict] = {}
    for lec_id in lecture_ids:
        eng = await playback_svc.get_lecture_engagement(db, [lec_id])
        pb_stats[lec_id] = {
            "replay_count": eng.replay_count,
            "rewind_count": eng.rewind_count,
            "pause_count":  eng.pause_count,
            "completion_pct": eng.avg_completion_pct,
        }

    topics: List[FeedbackTopic] = []
    for detected_topic, lec_id, count in rows:
        pb = pb_stats.get(lec_id, {})
        topics.append(
            FeedbackTopic(
                topic=detected_topic,
                question_count=count,
                percentage=round(count / total * 100, 1) if total > 0 else 0.0,
                lecture_id=lec_id if not lecture_id else None,
                lecture_title=lecture_title_map.get(lec_id) if not lecture_id else None,
                replay_count=pb.get("replay_count", 0),
                rewind_count=pb.get("rewind_count", 0),
                pause_count=pb.get("pause_count", 0),
                completion_pct=pb.get("completion_pct", 0.0),
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
