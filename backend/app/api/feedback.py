"""
Feedback / Analytics API — Teacher Dashboard + Student Lecture Ratings.

Teacher analytics endpoints (require role=teacher):
  GET  /api/feedback/overview                    → FeedbackOverview (all lectures or ?lecture_id=)
  GET  /api/feedback/topics                      → List[FeedbackTopic]
  GET  /api/feedback/lectures/{lecture_id}       → FeedbackOverview for one lecture
  GET  /api/feedback/lectures/{lecture_id}/ratings/analytics → RatingAnalytics
  GET  /api/feedback/lectures/{lecture_id}/ratings/reviews   → List[WrittenReview]
  GET  /api/feedback/engagement                  → LectureEngagementStats (all or ?lecture_id=)
  GET  /api/feedback/problem-solving             → ProblemSolvingStats (all or ?lecture_id=)
  GET  /api/feedback/teacher-score               → TeacherPerformanceScore

Student rating endpoints (require role=student):
  GET  /api/feedback/lectures/{lecture_id}/rating  → RatingRead | null (own rating)
  POST /api/feedback/lectures/{lecture_id}/rating  → RatingRead (create)
  PUT  /api/feedback/lectures/{lecture_id}/rating  → RatingRead (update)

Student playback endpoint (require role=student):
  POST /api/feedback/lectures/{lecture_id}/playback → 204 (flush batched events)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database.database import get_db
from app.database.models import Lecture, User
from app.schemas.feedback import (
    FeedbackOverview,
    FeedbackTopic,
    RatingCreate,
    RatingRead,
    RatingAnalytics,
    WrittenReview,
    ProblemSolvingStats,
    TeacherPerformanceScore,
)
from app.schemas.playback import PlaybackFlush, LectureEngagementStats
import app.services.feedback_service as feedback_svc
import app.services.rating_service as rating_svc
import app.services.playback_service as playback_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Ownership guard helpers
# ---------------------------------------------------------------------------

async def _verify_lecture_ownership(
    db: AsyncSession,
    lecture_id: str,
    teacher_id: str,
) -> None:
    """Raise 403/404 if the teacher does not own the lecture."""
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")
    if lecture.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="You do not own this lecture")


async def _verify_lecture_exists(
    db: AsyncSession,
    lecture_id: str,
) -> None:
    result = await db.execute(select(Lecture.id).where(Lecture.id == lecture_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")


# ---------------------------------------------------------------------------
# Teacher analytics endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/overview",
    response_model=FeedbackOverview,
    tags=["feedback"],
)
async def get_feedback_overview(
    lecture_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return aggregated overview statistics for the authenticated teacher.
    Includes engagement stats + rating summary + teacher performance score.
    Passing ?lecture_id=<id> scopes the result to that single lecture.
    """
    if lecture_id:
        await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await feedback_svc.get_overview(db, current_user.id, lecture_id=lecture_id)


@router.get(
    "/topics",
    response_model=List[FeedbackTopic],
    tags=["feedback"],
)
async def get_feedback_topics(
    lecture_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """Return per-topic breakdown with playback engagement data, sorted by question count."""
    if lecture_id:
        await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await feedback_svc.get_topics(db, current_user.id, lecture_id=lecture_id)


@router.get(
    "/lectures/{lecture_id}",
    response_model=FeedbackOverview,
    tags=["feedback"],
)
async def get_lecture_feedback(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """Return aggregated overview statistics scoped to one lecture."""
    await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await feedback_svc.get_lecture_overview(db, current_user.id, lecture_id)


@router.get(
    "/lectures/{lecture_id}/ratings/analytics",
    response_model=RatingAnalytics,
    tags=["feedback"],
)
async def get_lecture_rating_analytics(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """Return rating distribution analytics for a single lecture."""
    await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await rating_svc.get_rating_analytics(db, [lecture_id])


@router.get(
    "/lectures/{lecture_id}/ratings/reviews",
    response_model=List[WrittenReview],
    tags=["feedback"],
)
async def get_lecture_written_reviews(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return written feedback for a lecture (anonymized, teacher-only).
    Only rows with non-empty feedback text are returned.
    """
    await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await rating_svc.get_written_reviews(db, [lecture_id])


@router.get(
    "/engagement",
    response_model=LectureEngagementStats,
    tags=["feedback"],
)
async def get_engagement_stats(
    lecture_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return aggregated video playback engagement stats.
    Pass ?lecture_id= to scope to one lecture, or omit for all teacher lectures.
    """
    from sqlalchemy import select as sa_select
    from app.database.models import Lecture as LectureModel
    if lecture_id:
        await _verify_lecture_ownership(db, lecture_id, current_user.id)
        lecture_ids = [lecture_id]
    else:
        result = await db.execute(
            sa_select(LectureModel.id).where(LectureModel.teacher_id == current_user.id)
        )
        lecture_ids = list(result.scalars().all())
    return await playback_svc.get_lecture_engagement(db, lecture_ids)


@router.get(
    "/problem-solving",
    response_model=ProblemSolvingStats,
    tags=["feedback"],
)
async def get_problem_solving_stats(
    lecture_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return problem-solving (doubt response) analytics.
    Counts only student ↔ teacher doubt messages — not AI chat.
    """
    if lecture_id:
        await _verify_lecture_ownership(db, lecture_id, current_user.id)
    return await feedback_svc.get_problem_solving(db, current_user.id, lecture_id=lecture_id)


@router.get(
    "/teacher-score",
    response_model=TeacherPerformanceScore,
    tags=["feedback"],
)
async def get_teacher_performance_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """
    Return the calculated teacher performance score (0–5) with sub-scores.
    Score is always computed teacher-wide (not per-lecture).
    """
    return await feedback_svc.get_teacher_score(db, current_user.id)


# ---------------------------------------------------------------------------
# Student rating endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/lectures/{lecture_id}/rating",
    response_model=Optional[RatingRead],
    tags=["feedback", "student"],
)
async def student_get_rating(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated student's own rating for this lecture, or null.
    Accessible to both students and teachers (returns own record only).
    """
    return await rating_svc.get_student_rating(db, lecture_id, current_user.id)


@router.post(
    "/lectures/{lecture_id}/rating",
    response_model=RatingRead,
    status_code=201,
    tags=["feedback", "student"],
)
async def student_create_rating(
    lecture_id: str,
    payload: RatingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Create or update the student's rating for a lecture.
    Uses upsert: if a rating already exists it is updated, not duplicated.
    """
    return await rating_svc.upsert_student_rating(db, lecture_id, current_user.id, payload)


@router.put(
    "/lectures/{lecture_id}/rating",
    response_model=RatingRead,
    tags=["feedback", "student"],
)
async def student_update_rating(
    lecture_id: str,
    payload: RatingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Update the student's existing rating for a lecture.
    Uses the same upsert — creates if not exists.
    """
    return await rating_svc.upsert_student_rating(db, lecture_id, current_user.id, payload)


# ---------------------------------------------------------------------------
# Student playback endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/lectures/{lecture_id}/playback",
    status_code=204,
    tags=["feedback", "student"],
)
async def student_flush_playback(
    lecture_id: str,
    payload: PlaybackFlush,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """
    Receive a batched flush of video playback events from the student player.
    All counters are DELTA values for this session.
    This endpoint is fire-and-forget from the player (called on pause/unload).
    """
    await _verify_lecture_exists(db, lecture_id)
    await playback_svc.flush_playback(db, lecture_id, current_user.id, payload)
    response.status_code = 204
    return None
