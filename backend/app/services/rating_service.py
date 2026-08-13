"""
Rating service — Lecture Ratings (1–5 stars + optional written feedback).

Completely separate from:
  - chat_service  (Student ↔ Teacher doubts)
  - chatbot_service (Student ↔ AI chatbot)

Authorization:
  - Students may create/read/update their own rating for a lecture.
  - Teachers may read aggregated analytics + written reviews for their lectures.
  - No student can modify another student's rating.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LectureRating, Lecture
from app.schemas.feedback import (
    RatingCreate,
    RatingRead,
    RatingAnalytics,
    RatingDistribution,
    WrittenReview,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_read(r: LectureRating) -> RatingRead:
    return RatingRead(
        id=r.id,
        lecture_id=r.lecture_id,
        student_id=r.student_id,
        rating=r.rating,
        feedback=r.feedback,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


async def _get_lecture_or_404(db: AsyncSession, lecture_id: str) -> Lecture:
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


# ---------------------------------------------------------------------------
# Student operations
# ---------------------------------------------------------------------------

async def get_student_rating(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
) -> Optional[RatingRead]:
    """Return the student's own rating for this lecture, or None."""
    result = await db.execute(
        select(LectureRating).where(
            LectureRating.lecture_id == lecture_id,
            LectureRating.student_id == student_id,
        )
    )
    row = result.scalar_one_or_none()
    return _to_read(row) if row else None


async def upsert_student_rating(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
    payload: RatingCreate,
) -> RatingRead:
    """
    Create or update the student's rating for a lecture.

    Uses SELECT-then-INSERT/UPDATE to enforce the one-per-student constraint
    without relying on DB exceptions (avoids transaction abort in asyncpg).
    """
    await _get_lecture_or_404(db, lecture_id)

    result = await db.execute(
        select(LectureRating).where(
            LectureRating.lecture_id == lecture_id,
            LectureRating.student_id == student_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        rating_row = LectureRating(
            lecture_id=lecture_id,
            student_id=student_id,
            rating=payload.rating,
            feedback=payload.feedback,
        )
        db.add(rating_row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Race: another request inserted first — fetch and update instead
            result2 = await db.execute(
                select(LectureRating).where(
                    LectureRating.lecture_id == lecture_id,
                    LectureRating.student_id == student_id,
                )
            )
            existing = result2.scalar_one()
            existing.rating = payload.rating
            existing.feedback = payload.feedback
            existing.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(existing)
            return _to_read(existing)
        await db.refresh(rating_row)
        return _to_read(rating_row)
    else:
        existing.rating = payload.rating
        existing.feedback = payload.feedback
        existing.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return _to_read(existing)


# ---------------------------------------------------------------------------
# Teacher analytics operations
# ---------------------------------------------------------------------------

async def get_rating_analytics(
    db: AsyncSession,
    lecture_ids: List[str],
) -> RatingAnalytics:
    """
    Return aggregated rating analytics for a set of lecture IDs.
    Returns a zero-state RatingAnalytics when there are no ratings.
    """
    if not lecture_ids:
        return RatingAnalytics()

    # Aggregate: count per star level + avg
    agg_stmt = (
        select(
            func.count(LectureRating.id).label("total"),
            func.avg(LectureRating.rating).label("avg"),
            func.sum(
                func.cast(LectureRating.rating == 5, type_=func.count(LectureRating.id).type)
            ).label("five"),
            func.sum(
                func.cast(LectureRating.rating == 4, type_=func.count(LectureRating.id).type)
            ).label("four"),
            func.sum(
                func.cast(LectureRating.rating == 3, type_=func.count(LectureRating.id).type)
            ).label("three"),
            func.sum(
                func.cast(LectureRating.rating == 2, type_=func.count(LectureRating.id).type)
            ).label("two"),
            func.sum(
                func.cast(LectureRating.rating == 1, type_=func.count(LectureRating.id).type)
            ).label("one"),
        )
        .where(LectureRating.lecture_id.in_(lecture_ids))
    )
    # Use a simpler approach: individual counts per star level
    total_stmt = (
        select(func.count(LectureRating.id), func.avg(LectureRating.rating))
        .where(LectureRating.lecture_id.in_(lecture_ids))
    )
    total_result = await db.execute(total_stmt)
    total_row = total_result.first()
    total_count: int = total_row[0] if total_row else 0
    avg_val: Optional[float] = float(round(total_row[1], 2)) if total_row and total_row[1] else None

    if total_count == 0:
        return RatingAnalytics()

    # Per-star counts
    dist: dict[int, int] = {}
    for star in (1, 2, 3, 4, 5):
        star_stmt = (
            select(func.count(LectureRating.id))
            .where(
                LectureRating.lecture_id.in_(lecture_ids),
                LectureRating.rating == star,
            )
        )
        star_result = await db.execute(star_stmt)
        dist[star] = star_result.scalar_one() or 0

    return RatingAnalytics(
        avg_rating=avg_val,
        total_ratings=total_count,
        distribution=RatingDistribution(
            five=dist[5],
            four=dist[4],
            three=dist[3],
            two=dist[2],
            one=dist[1],
        ),
    )


async def get_written_reviews(
    db: AsyncSession,
    lecture_ids: List[str],
    limit: int = 50,
) -> List[WrittenReview]:
    """
    Return written feedback for a set of lectures, newest first.
    Only returns rows that have non-empty feedback text.
    Student identity is NOT returned.
    """
    if not lecture_ids:
        return []

    stmt = (
        select(LectureRating.rating, LectureRating.feedback, LectureRating.created_at)
        .where(
            LectureRating.lecture_id.in_(lecture_ids),
            LectureRating.feedback.isnot(None),
            LectureRating.feedback != "",
        )
        .order_by(LectureRating.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        WrittenReview(rating=row[0], feedback=row[1], created_at=row[2])
        for row in result.all()
    ]


async def get_lecture_rating_summary(
    db: AsyncSession,
    lecture_ids: List[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Return (most_rated_lecture_title, lowest_rated_lecture_title).
    Used in the teacher overview panel.
    """
    if not lecture_ids:
        return None, None

    stmt = (
        select(LectureRating.lecture_id, func.avg(LectureRating.rating).label("avg_r"))
        .where(LectureRating.lecture_id.in_(lecture_ids))
        .group_by(LectureRating.lecture_id)
        .having(func.count(LectureRating.id) > 0)
        .order_by(func.avg(LectureRating.rating).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return None, None

    best_id = rows[0][0]
    worst_id = rows[-1][0]

    # Fetch titles
    from app.database.models import Lecture as LectureModel
    titles_result = await db.execute(
        select(LectureModel.id, LectureModel.title)
        .where(LectureModel.id.in_([best_id, worst_id]))
    )
    title_map = {r[0]: r[1] for r in titles_result.all()}

    best_title = title_map.get(best_id)
    worst_title = title_map.get(worst_id) if worst_id != best_id else None
    return best_title, worst_title
