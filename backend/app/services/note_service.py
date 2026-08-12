"""
Note Service — Phase 8

Thin async database layer for NoteModel.
Supports multi-language notes with proper upsert logic.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database.models import NoteModel
from app.schemas.notes import NoteRead


# Supported languages
SUPPORTED_LANGUAGES = {"english", "hindi", "hinglish"}


def _validate_language(language: str) -> str:
    """Validate and normalize language parameter."""
    lang = language.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {lang}. "
            f"Must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
        )
    return lang


def _to_schema(row: NoteModel) -> NoteRead:
    return NoteRead(
        note_id=row.id,
        lecture_id=row.lecture_id,
        content=row.content,
        language=row.language,
        created_at=row.created_at,
    )


async def save_note(
    db: AsyncSession,
    lecture_id: str,
    content: str,
    language: str = "english",
) -> NoteRead:
    """
    Persist a generated notes document for a lecture.
    
    If a note already exists for the given lecture_id + language,
    it will be updated. Otherwise, a new note is created.
    
    Args:
        db: Database session
        lecture_id: ID of the lecture
        content: The notes content
        language: Language code (english, hindi, hinglish)
    
    Returns:
        The created or updated note
    
    Raises:
        ValueError: If language is not supported
    """
    language = _validate_language(language)
    
    # Check if a note already exists for this lecture+language
    stmt = select(NoteModel).where(
        (NoteModel.lecture_id == lecture_id) &
        (NoteModel.language == language)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing note
        existing.content = content
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return _to_schema(existing)
    else:
        # Create new note
        row = NoteModel(
            id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            content=content,
            language=language,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)


async def get_notes(
    db: AsyncSession,
    lecture_id: str,
    language: Optional[str] = None,
) -> List[NoteRead]:
    """
    Return all notes for a lecture, ordered by creation time.

    If *language* is given, filter to that language only.
    
    Args:
        db: Database session
        lecture_id: ID of the lecture
        language: Optional language code to filter by
    
    Returns:
        List of notes for the lecture
    
    Raises:
        ValueError: If language parameter is not supported
    """
    if language:
        language = _validate_language(language)
    
    stmt = (
        select(NoteModel)
        .where(NoteModel.lecture_id == lecture_id)
        .order_by(NoteModel.created_at)
    )
    if language:
        stmt = stmt.where(NoteModel.language == language)
    
    result = await db.execute(stmt)
    return [_to_schema(row) for row in result.scalars().all()]


async def get_note(
    db: AsyncSession,
    lecture_id: str,
    language: str = "english",
) -> Optional[NoteRead]:
    """
    Get a specific note for a lecture and language.
    
    Args:
        db: Database session
        lecture_id: ID of the lecture
        language: Language code
    
    Returns:
        The note if found, None otherwise
    
    Raises:
        ValueError: If language is not supported
    """
    language = _validate_language(language)
    
    stmt = select(NoteModel).where(
        (NoteModel.lecture_id == lecture_id) &
        (NoteModel.language == language)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return _to_schema(row) if row else None


async def delete_note(
    db: AsyncSession,
    lecture_id: str,
    language: str = "english",
) -> bool:
    """
    Delete a specific note for a lecture and language.
    
    Args:
        db: Database session
        lecture_id: ID of the lecture
        language: Language code
    
    Returns:
        True if a note was deleted, False if none existed
    
    Raises:
        ValueError: If language is not supported
    """
    language = _validate_language(language)
    
    stmt = delete(NoteModel).where(
        (NoteModel.lecture_id == lecture_id) &
        (NoteModel.language == language)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

