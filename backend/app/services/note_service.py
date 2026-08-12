"""
Note Service — Phase 8

Thin async database layer for NoteModel.
"""
from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import NoteModel
from app.schemas.notes import NoteRead


def _to_schema(row: NoteModel) -> NoteRead:
    return NoteRead(
        note_id=row.id,
        lecture_id=row.lecture_id,
        content=row.content,
        created_at=row.created_at,
    )


async def save_note(db: AsyncSession, lecture_id: str, content: str) -> NoteRead:
    """Persist a generated notes document for a lecture."""
    row = NoteModel(
        id=str(uuid.uuid4()),
        lecture_id=lecture_id,
        content=content,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_schema(row)


async def get_notes(db: AsyncSession, lecture_id: str) -> List[NoteRead]:
    """Return all notes for a lecture, ordered by creation time."""
    stmt = (
        select(NoteModel)
        .where(NoteModel.lecture_id == lecture_id)
        .order_by(NoteModel.created_at)
    )
    result = await db.execute(stmt)
    return [_to_schema(row) for row in result.scalars().all()]
