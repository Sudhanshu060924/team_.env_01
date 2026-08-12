import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LectureEventModel
from app.schemas.events import LectureEvent


def _to_schema(row: LectureEventModel) -> LectureEvent:
    return LectureEvent(
        event_id=row.id,
        lecture_id=row.lecture_id,
        timestamp=row.timestamp,
        type=row.type,
        source=row.source,
        content=row.content,
        metadata=row.metadata_ or {},
    )


async def save_event(db: AsyncSession, event: LectureEvent) -> LectureEvent:
    """Persist a LectureEvent to the database."""
    row = LectureEventModel(
        id=event.event_id or str(uuid.uuid4()),
        lecture_id=event.lecture_id,
        timestamp=event.timestamp,
        type=event.type,
        source=event.source,
        content=event.content,
        metadata_=event.metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_schema(row)


async def get_events(
    db: AsyncSession,
    lecture_id: str,
    event_type: Optional[str] = None,
) -> List[LectureEvent]:
    stmt = (
        select(LectureEventModel)
        .where(LectureEventModel.lecture_id == lecture_id)
        .order_by(LectureEventModel.timestamp)
    )
    if event_type:
        stmt = stmt.where(LectureEventModel.type == event_type)
    result = await db.execute(stmt)
    return [_to_schema(row) for row in result.scalars().all()]
