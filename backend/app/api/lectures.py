from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.schemas.lecture import LectureCreate, LectureRead
from app.schemas.events import LectureEvent
from app.schemas.notes import NoteRead
from app.schemas.qa import QuestionRequest, QuestionResponse
import app.services.lecture_service as lecture_svc
import app.services.event_service as event_svc

router = APIRouter()


@router.post("/start", response_model=LectureRead, status_code=201)
async def start_lecture(payload: LectureCreate, db: AsyncSession = Depends(get_db)):
    """Create a new lecture session."""
    return await lecture_svc.create_lecture(db, payload)


@router.get("/{lecture_id}", response_model=LectureRead)
async def get_lecture(lecture_id: str, db: AsyncSession = Depends(get_db)):
    lecture = await lecture_svc.get_lecture(db, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


@router.post("/{lecture_id}/complete", response_model=LectureRead)
async def complete_lecture(lecture_id: str, db: AsyncSession = Depends(get_db)):
    lecture = await lecture_svc.complete_lecture(db, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


@router.get("/{lecture_id}/events", response_model=List[LectureEvent])
async def get_events(
    lecture_id: str,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await event_svc.get_events(db, lecture_id, event_type=type)


@router.get("/{lecture_id}/notes", response_model=List[NoteRead])
async def get_notes(lecture_id: str, db: AsyncSession = Depends(get_db)):
    """Return generated notes for a lecture. Notes are created by the Notes Agent (Phase 8)."""
    # Phase 2: return empty list; Phase 8 will populate
    return []


@router.post("/{lecture_id}/questions", response_model=QuestionResponse)
async def ask_question(
    lecture_id: str,
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Q&A endpoint — Phase 9 will wire LangGraph here."""
    return QuestionResponse(
        answer="Q&A agent not yet active. Coming in Phase 9.",
        sources=[],
    )
