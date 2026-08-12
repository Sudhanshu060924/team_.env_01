import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Lecture
from app.schemas.lecture import LectureCreate, LectureRead


def _to_read(lecture: Lecture) -> LectureRead:
    return LectureRead(
        lecture_id=lecture.id,
        title=lecture.title,
        video_name=lecture.video_name,
        status=lecture.status,
        created_at=lecture.created_at,
        completed_at=lecture.completed_at,
    )


async def create_lecture(db: AsyncSession, payload: LectureCreate) -> LectureRead:
    lecture = Lecture(
        id=str(uuid.uuid4()),
        title=payload.title,
        video_name=payload.video_name,
        status="live",
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
    result = await db.execute(select(Lecture).order_by(Lecture.created_at.desc()))
    return [_to_read(row) for row in result.scalars().all()]
