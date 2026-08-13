"""
Notes Generation Graph — Phase 8

Entry point called by the WebSocket handler when a lecture completes,
or when a student requests notes in a different language.

Pipeline:
  1. Fetch all speech + board LectureEvents from the DB.
  2. Call the Notes Generation node (Groq LLM) with the target language.
  3. Save the resulting Markdown to the notes table.
  4. Broadcast a 'notes' WebSocket message to all connected clients.
"""
from __future__ import annotations

import logging

from app.database.database import get_db
import app.services.event_service as event_svc
import app.services.note_service as note_svc
from app.graph.nodes.notes import generate_notes
from app.services.websocket_manager import manager
from app.services.lecture_session import session_store

logger = logging.getLogger(__name__)


async def run_notes_graph(lecture_id: str, target_language: str = "") -> None:
    """
    Generate and persist structured notes for a completed lecture.

    If *target_language* is empty, the current session language is used
    (defaulting to "english" if no session exists).

    This runs as a background asyncio task — any exception is logged but
    never propagated so the WS session is never disrupted.
    """
    try:
        # Resolve language — prefer explicit arg, then session, then default
        if not target_language:
            state = session_store.get(lecture_id)
            target_language = state.target_language if state else "english"

        # 1. Fetch all usable events (speech + board)
        events = []
        async for db in get_db():
            events = await event_svc.get_events(db, lecture_id)

        speech_and_board = [
            ev for ev in events if ev.type in ("speech", "speech_event", "board", "ocr")
        ]

        if not speech_and_board:
            logger.info("Notes generation skipped: no speech/board events for lecture_id=%s", lecture_id)
            return

        # 2. Generate notes via Groq (language-aware)
        notes_md = await generate_notes(lecture_id, speech_and_board, target_language=target_language)
        if not notes_md:
            return

        # 3. Persist to DB
        async for db in get_db():
            await note_svc.save_note(db, lecture_id, notes_md, language=target_language)

        # 4. Broadcast to connected clients
        await manager.broadcast(lecture_id, {
            "type":       "notes",
            "lecture_id": lecture_id,
            "content":    notes_md,
            "language":   target_language,
        })

        logger.info(
            "Notes broadcast to lecture_id=%s language=%s (%d chars)",
            lecture_id, target_language, len(notes_md),
        )

    except Exception as exc:
        logger.error("run_notes_graph failed for lecture_id=%s: %s", lecture_id, exc, exc_info=True)
