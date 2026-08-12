import os
import tempfile
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_current_user, get_current_user, require_role
from app.database.database import get_db
from app.database.models import User
from app.schemas.lecture import LectureCreate, LectureRead
from app.schemas.events import LectureEvent
from app.schemas.notes import NoteRead
from app.schemas.qa import QuestionRequest, QuestionResponse
import app.services.lecture_service as lecture_svc
import app.services.event_service as event_svc
import app.services.note_service as note_svc

logger = logging.getLogger(__name__)

# Allowed video MIME types and extensions for upload
_ALLOWED_MIME_PREFIXES = ("video/",)
_ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
_MAX_FILE_BYTES = 500 * 1024 * 1024  # 500 MB

router = APIRouter()


# ---------------------------------------------------------------------------
# Unrestricted list + create (legacy / live pipeline)
# ---------------------------------------------------------------------------

@router.get("", response_model=List[LectureRead])
async def list_lectures(db: AsyncSession = Depends(get_db)):
    """Return all lectures ordered by creation date descending."""
    return await lecture_svc.list_lectures(db)


@router.post("/start", response_model=LectureRead, status_code=201)
async def start_lecture(
    payload: LectureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Create a new lecture session.

    If the caller is authenticated, teacher_id is set to their user id.
    Unauthenticated calls (legacy / tests) create the lecture with teacher_id=NULL.
    """
    teacher_id = current_user.id if current_user else None
    return await lecture_svc.create_lecture(db, payload, teacher_id=teacher_id)


# ---------------------------------------------------------------------------
# Student endpoints — MUST come before /{lecture_id} to avoid route clash
# ---------------------------------------------------------------------------

@router.get("/student/lectures", response_model=List[LectureRead], tags=["student"])
async def student_list_lectures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """Return completed lectures accessible to the authenticated student."""
    return await lecture_svc.list_student_lectures(db)


@router.get("/student/lectures/{lecture_id}", response_model=LectureRead, tags=["student"])
async def student_get_lecture(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """Return a completed lecture accessible to the authenticated student."""
    lecture = await lecture_svc.get_lecture_for_student(db, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


# ---------------------------------------------------------------------------
# Teacher endpoints — MUST come before /{lecture_id} to avoid route clash
# ---------------------------------------------------------------------------

@router.get("/teacher/lectures", response_model=List[LectureRead], tags=["teacher"])
async def teacher_list_lectures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """Return lectures owned by the authenticated teacher."""
    return await lecture_svc.list_teacher_lectures(db, current_user.id)


# ---------------------------------------------------------------------------
# Video upload — authenticated teacher (or any authenticated user for MVP)
# ---------------------------------------------------------------------------

@router.post("/{lecture_id}/video", response_model=LectureRead, tags=["video"])
async def upload_lecture_video(
    lecture_id: str,
    video: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a video file for an existing lecture.

    - Authenticated user must be the lecture's owner (teacher_id) or a teacher.
    - File is validated (type, extension, size) before upload.
    - Video is uploaded to Cloudinary; the resulting secure_url and public_id
      are persisted on the lecture row.
    - The Cloudinary API secret is NEVER returned to the caller.
    """
    # ------------------------------------------------------------------
    # 1. Fetch the lecture and verify ownership
    # ------------------------------------------------------------------
    lecture = await lecture_svc.get_lecture(db, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    if lecture.teacher_id is not None and lecture.teacher_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not the owner of this lecture",
        )

    # ------------------------------------------------------------------
    # 2. Validate the uploaded file
    # ------------------------------------------------------------------
    filename = video.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content_type = video.content_type or ""
    if not any(content_type.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported content-type '{content_type}'. Expected a video file.",
        )

    # ------------------------------------------------------------------
    # 3. Read file and enforce size limit
    # ------------------------------------------------------------------
    file_bytes = await video.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {_MAX_FILE_BYTES // (1024 * 1024)} MB",
        )

    # ------------------------------------------------------------------
    # 4. Upload to Cloudinary via a temp file
    # ------------------------------------------------------------------
    from app.integrations.cloudinary_service import CloudinaryVideoService, CloudinaryUploadError

    try:
        svc = CloudinaryVideoService()
        # Write to a named temp file so Cloudinary SDK can detect the format
        suffix = ext if ext else ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            secure_url, public_id = svc.upload_video(tmp_path, lecture_id)
        finally:
            os.unlink(tmp_path)
    except CloudinaryUploadError as exc:
        logger.error("Cloudinary upload error for lecture %s: %s", lecture_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Unable to upload video. Please try again.",
        ) from exc

    # ------------------------------------------------------------------
    # 5. Persist video metadata on the lecture
    # ------------------------------------------------------------------
    updated = await lecture_svc.attach_video(
        db,
        lecture_id=lecture_id,
        video_url=secure_url,
        cloudinary_public_id=public_id,
        video_name=filename or None,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Lecture not found after upload")

    return updated


# ---------------------------------------------------------------------------
# Unrestricted per-lecture endpoints (legacy + live pipeline)
# ---------------------------------------------------------------------------

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
async def get_notes(
    lecture_id: str,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return generated notes for a lecture (produced by the Notes Agent).

    Optional query param: ?language=hindi  — filter to notes in that language.
    """
    return await note_svc.get_notes(db, lecture_id, language=language)


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
