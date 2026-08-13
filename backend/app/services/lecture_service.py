import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Lecture
from app.schemas.lecture import LectureCreate, LectureRead

# Statuses visible to students (video has been uploaded or lecture is completed)
_STUDENT_VISIBLE_STATUSES = ("available", "completed")


async def attach_video(
    db: AsyncSession,
    lecture_id: str,
    video_url: str,
    cloudinary_public_id: str,
    video_name: Optional[str] = None,
) -> Optional[LectureRead]:
    """
    Persist Cloudinary video metadata on an existing lecture and mark it
    as 'available' so students can access it.

    If video_name is provided it also updates the display name.
    Returns the updated LectureRead, or None if the lecture does not exist.
    """
    result = await db.execute(
        select(Lecture).where(Lecture.id == lecture_id).options(selectinload(Lecture.teacher))
    )
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    lecture.video_url = video_url
    lecture.cloudinary_public_id = cloudinary_public_id
    if video_name is not None:
        lecture.video_name = video_name
    # Mark as available so students can see it
    if lecture.status not in ("completed",):
        lecture.status = "available"
    await db.commit()
    await db.refresh(lecture)
    return _to_read(lecture)


def _to_read(lecture: Lecture) -> LectureRead:
    teacher_name: Optional[str] = None
    try:
        # teacher is eagerly loaded when queried with selectinload;
        # fall back gracefully when the relationship is not yet loaded
        # (e.g. immediately after db.refresh which doesn't load relations).
        t = lecture.__dict__.get("teacher")
        if t is not None:
            teacher_name = t.name
    except Exception:
        pass
    return LectureRead(
        lecture_id=lecture.id,
        title=lecture.title,
        video_name=lecture.video_name,
        status=lecture.status,
        teacher_id=lecture.teacher_id,
        teacher_name=teacher_name,
        created_at=lecture.created_at,
        completed_at=lecture.completed_at,
        video_url=lecture.video_url,
        cloudinary_public_id=lecture.cloudinary_public_id,
    )


async def create_lecture(
    db: AsyncSession,
    payload: LectureCreate,
    teacher_id: Optional[str] = None,
) -> LectureRead:
    """Create a new lecture. teacher_id is set from the authenticated user."""
    lecture = Lecture(
        id=str(uuid.uuid4()),
        title=payload.title,
        video_name=payload.video_name or "",
        status="live",
        teacher_id=teacher_id,
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return _to_read(lecture)


async def get_lecture(db: AsyncSession, lecture_id: str) -> Optional[LectureRead]:
    result = await db.execute(
        select(Lecture).where(Lecture.id == lecture_id).options(selectinload(Lecture.teacher))
    )
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    return _to_read(lecture)


async def complete_lecture(db: AsyncSession, lecture_id: str) -> Optional[LectureRead]:
    result = await db.execute(
        select(Lecture).where(Lecture.id == lecture_id).options(selectinload(Lecture.teacher))
    )
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    lecture.status = "completed"
    lecture.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(lecture)
    return _to_read(lecture)


async def list_lectures(db: AsyncSession) -> List[LectureRead]:
    """Return all lectures (unrestricted — used by legacy endpoints)."""
    result = await db.execute(
        select(Lecture).options(selectinload(Lecture.teacher)).order_by(Lecture.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]


async def list_student_lectures(db: AsyncSession) -> List[LectureRead]:
    """Return lectures visible to students (available or completed, with a video)."""
    from sqlalchemy import or_
    result = await db.execute(
        select(Lecture)
        .options(selectinload(Lecture.teacher))
        .where(
            or_(*(Lecture.status == s for s in _STUDENT_VISIBLE_STATUSES)),
            Lecture.video_url.isnot(None),
        )
        .order_by(Lecture.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]


async def list_teacher_lectures(db: AsyncSession, teacher_id: str) -> List[LectureRead]:
    """Return lectures owned by this teacher."""
    result = await db.execute(
        select(Lecture)
        .options(selectinload(Lecture.teacher))
        .where(Lecture.teacher_id == teacher_id)
        .order_by(Lecture.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]


async def get_lecture_for_student(
    db: AsyncSession,
    lecture_id: str,
) -> Optional[LectureRead]:
    """
    Return a lecture only if it is accessible to students (available or completed).
    Returns None if not found or not yet published.
    """
    from sqlalchemy import or_
    result = await db.execute(
        select(Lecture)
        .options(selectinload(Lecture.teacher))
        .where(
            Lecture.id == lecture_id,
            or_(*(Lecture.status == s for s in _STUDENT_VISIBLE_STATUSES)),
        )
    )
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    return _to_read(lecture)
