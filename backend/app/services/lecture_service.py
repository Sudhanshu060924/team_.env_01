import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Lecture
from app.schemas.lecture import LectureCreate, LectureRead


async def attach_video(
    db: AsyncSession,
    lecture_id: str,
    video_url: str,
    cloudinary_public_id: str,
    video_name: Optional[str] = None,
) -> Optional[LectureRead]:
    """
    Persist Cloudinary video metadata on an existing lecture.

    If video_name is provided it also updates the display name.
    Returns the updated LectureRead, or None if the lecture does not exist.
    """
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    lecture.video_url = video_url
    lecture.cloudinary_public_id = cloudinary_public_id
    if video_name is not None:
        lecture.video_name = video_name
    await db.commit()
    await db.refresh(lecture)
    return _to_read(lecture)


def _to_read(lecture: Lecture) -> LectureRead:
    return LectureRead(
        lecture_id=lecture.id,
        title=lecture.title,
        video_name=lecture.video_name,
        status=lecture.status,
        teacher_id=lecture.teacher_id,
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
        video_name=payload.video_name,
        status="live",
        teacher_id=teacher_id,
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return _to_read(lecture)


async def get_lecture(db: AsyncSession, lecture_id: str) -> Optional[LectureRead]:
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    return _to_read(lecture)


async def complete_lecture(db: AsyncSession, lecture_id: str) -> Optional[LectureRead]:
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
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
    result = await db.execute(select(Lecture).order_by(Lecture.created_at.desc()))
    return [_to_read(row) for row in result.scalars().all()]


async def list_student_lectures(db: AsyncSession) -> List[LectureRead]:
    """Return completed/published lectures visible to students."""
    result = await db.execute(
        select(Lecture)
        .where(Lecture.status == "completed")
        .order_by(Lecture.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]


async def list_teacher_lectures(db: AsyncSession, teacher_id: str) -> List[LectureRead]:
    """Return lectures owned by this teacher."""
    result = await db.execute(
        select(Lecture)
        .where(Lecture.teacher_id == teacher_id)
        .order_by(Lecture.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]


async def get_lecture_for_student(
    db: AsyncSession,
    lecture_id: str,
) -> Optional[LectureRead]:
    """
    Return a lecture only if it is completed (i.e. accessible by students).
    Returns None if not found or not yet completed.
    """
    result = await db.execute(
        select(Lecture).where(
            Lecture.id == lecture_id,
            Lecture.status == "completed",
        )
    )
    lecture = result.scalar_one_or_none()
    if lecture is None:
        return None
    return _to_read(lecture)
