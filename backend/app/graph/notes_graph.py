"""
Notes Generation Graph — Phase 8

Entry point called by the WebSocket handler when a lecture completes.

Pipeline:
  1. Fetch all speech + board LectureEvents from the DB.
  2. Call the Notes Generation node (Groq LLM).
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

logger = logging.getLogger(__name__)


async def run_notes_graph(lecture_id: str) -> None:
    """
    Generate and persist structured notes for a completed lecture.

    This runs as a background asyncio task — any exception is logged but
    never propagated so the WS session is never disrupted.
    """
    try:

        # 1. Fetch all usable events (speech + board)
        events = []
        async for db in get_db():
            events = await event_svc.get_events(db, lecture_id)

        speech_and_board = [
            ev for ev in events if ev.type in ("speech", "board", "ocr")
        ]

        if not speech_and_board:
            logger.info("Notes generation skipped: no speech/board events for lecture_id=%s", lecture_id)
            return

        # 2. Generate notes via Groq
        notes_md = await generate_notes(lecture_id, speech_and_board)
        if not notes_md:
            return

        # 3. Persist to DB
        async for db in get_db():
            await note_svc.save_note(db, lecture_id, notes_md)

        # 4. Broadcast to connected clients
        await manager.broadcast(lecture_id, {
            "type":       "notes",
            "lecture_id": lecture_id,
            "content":    notes_md,
        })

        logger.info("Notes broadcast to lecture_id=%s (%d chars)", lecture_id, len(notes_md))

    except Exception as exc:
        logger.error("run_notes_graph failed for lecture_id=%s: %s", lecture_id, exc, exc_info=True)
