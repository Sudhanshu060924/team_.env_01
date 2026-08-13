"""
Feedback / Analytics API — Teacher Dashboard + Student Lecture Ratings.

Teacher analytics endpoints (require role=teacher):
  GET  /api/feedback/overview                    → FeedbackOverview (all lectures or ?lecture_id=)
  GET  /api/feedback/topics                      → List[FeedbackTopic]
  GET  /api/feedback/lectures/{lecture_id}       → FeedbackOverview for one lecture
  GET  /api/feedback/lectures/{lecture_id}/ratings/analytics → RatingAnalytics
  GET  /api/feedback/lectures/{lecture_id}/ratings/reviews   → List[WrittenReview]

Student rating endpoints (require role=student):
  GET  /api/feedback/lectures/{lecture_id}/rating  → RatingRead | null (own rating)
  POST /api/feedback/lectures/{lecture_id}/rating  → RatingRead (create)
  PUT  /api/feedback/lectures/{lecture_id}/rating  → RatingRead (update)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
)
import app.services.feedback_service as feedback_svc
import app.services.rating_service as rating_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Ownership guard helper
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
    Includes engagement stats + rating summary.
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
    """Return per-topic breakdown sorted by question count descending."""
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
