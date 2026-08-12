"""
WebSocket endpoint: /ws/lectures/{lecture_id}

Message protocol (client → server):
  { "type": "audio_chunk",       "lecture_id": "...", "timestamp": 12.5, "data": "<base64>", "filename": "audio.webm" }
  { "type": "frame",             "lecture_id": "...", "timestamp": 14.0, "data": "<base64>" }
  { "type": "lecture_completed", "lecture_id": "...", "timestamp": 3600 }
  { "type": "language_change",   "lecture_id": "...", "target_language": "hinglish" }
  { "type": "question",          "lecture_id": "...", "content": "..." }
  { "type": "ping" }

Message protocol (server → client):
  { "type": "connected",         "lecture_id": "...", "message": "..." }
  { "type": "speech_event",      "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {...} }
  { "type": "translation",       "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {"language": "...", "source": "translation_agent"} }
  { "type": "translation_error", "lecture_id": "...", "timestamp": ..., "message": "Translation temporarily unavailable" }
  { "type": "topic_update",      "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {...} }
  { "type": "important_event",   "lecture_id": "...", "timestamp": ..., "content": "..." }
  { "type": "notes",             "lecture_id": "...", "content": "..." }
  { "type": "answer",            "lecture_id": "...", "content": "..." }
  { "type": "error",             "message": "..." }
  { "type": "pong" }
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.services.websocket_manager import manager
from app.graph.state import VALID_LANGUAGES
from app.services.lecture_session import session_store
from app.graph.nodes.translation import translate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/lectures/{lecture_id}")
async def websocket_endpoint(websocket: WebSocket, lecture_id: str):
    await manager.connect(lecture_id, websocket)

    # Ensure a session state exists for this lecture
    session_store.get_or_create(lecture_id)

    # Confirm connection
    await manager.send_personal(websocket, {
        "type": "connected",
        "lecture_id": lecture_id,
        "message": f"Connected to lecture {lecture_id}",
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            # ── ping / keepalive ────────────────────────────────────────
            if msg_type == "ping":
                await manager.send_personal(websocket, {"type": "pong"})
                continue

            # ── audio chunk → speech + translation pipeline ─────────────
            if msg_type == "audio_chunk":
                asyncio.create_task(
                    _handle_audio(lecture_id, data)
                )
                continue

            # ── video frame → vision pipeline ──────────────────────────
            if msg_type == "frame":
                asyncio.create_task(
                    _handle_frame(lecture_id, data)
                )
                continue

            # ── lecture completed → notes generation ───────────────────
            if msg_type == "lecture_completed":
                asyncio.create_task(
                    _handle_lecture_completed(lecture_id, data)
                )
                continue

            # ── student language selection change ──────────────────────
            if msg_type == "language_change":
                asyncio.create_task(
                    _handle_language_change(lecture_id, data, websocket)
                )
                continue

            # ── student question via WebSocket ─────────────────────────
            if msg_type == "question":
                asyncio.create_task(
                    _handle_question(lecture_id, data, websocket)
                )
                continue

            logger.debug("WS unknown message type=%s lecture=%s", msg_type, lecture_id)

    except WebSocketDisconnect:
        manager.disconnect(lecture_id, websocket)
    except Exception as exc:
        logger.error("WS error lecture=%s: %s", lecture_id, exc)
        if websocket.client_state == WebSocketState.CONNECTED:
            await manager.send_personal(websocket, {"type": "error", "message": str(exc)})
        manager.disconnect(lecture_id, websocket)


# ---------------------------------------------------------------------------
# Background task handlers
# ---------------------------------------------------------------------------

async def _handle_audio(lecture_id: str, data: dict) -> None:
    """
    1. Decode audio bytes
    2. Transcribe via Groq Whisper (with FFmpeg preprocessing)
    3. Persist speech LectureEvent
    4. Broadcast speech_event
    5. Update session context + run Translation Agent
    6. Broadcast translation event
    """
    timestamp = data.get("timestamp", 0.0)
    audio_b64 = data.get("data", "")

    try:
        import base64
        from app.services.speech_service import transcribe_audio
        from app.schemas.events import LectureEvent
        from app.database.database import get_db
        import app.services.event_service as event_svc

        audio_bytes = base64.b64decode(audio_b64)
        filename = data.get("filename", "audio.webm")
        result = await transcribe_audio(audio_bytes, filename=filename)
        text = result.get("text", "").strip()
        if not text:
            return

        event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=timestamp,
            type="speech",
            source="whisper",
            content=text,
            metadata={"language": result.get("language", "en")},
        )

        # Persist
        async for db in get_db():
            await event_svc.save_event(db, event)

        # Broadcast raw transcript to UI
        await manager.broadcast(lecture_id, {
            "type": "speech_event",
            "lecture_id": lecture_id,
            "timestamp": timestamp,
            "content": text,
            "metadata": event.metadata,
        })

        # ── Translation pipeline ────────────────────────────────────
        asyncio.create_task(
            _run_translation(lecture_id, text, timestamp)
        )

    except Exception as exc:
        logger.error("Audio handler error lecture=%s: %s", lecture_id, exc, exc_info=True)
        await manager.broadcast(lecture_id, {"type": "error", "message": f"Speech error: {exc}"})


async def _run_translation(lecture_id: str, transcript: str, timestamp: float) -> None:
    """
    Update session context and call the Translation Agent.
    Runs as a separate task so it never blocks the next audio chunk.
    """
    try:
        # Update bounded context window
        state = session_store.add_transcript(lecture_id, transcript, timestamp)

        result = await translate(state)
        if not result:
            # Translation returned nothing (e.g. API key missing) — skip broadcast
            return

        translated = result["translated"]
        lang       = result["language"]

        # Persist the translation back into session for next-turn context
        session_store.set_translation(lecture_id, translated)

        await manager.broadcast(lecture_id, {
            "type":      "translation",
            "lecture_id": lecture_id,
            "timestamp":  timestamp,
            "content":    translated,
            "metadata":  {"language": lang, "source": "translation_agent"},
        })

    except Exception as exc:
        logger.error("Translation pipeline error lecture=%s: %s", lecture_id, exc, exc_info=True)
        await manager.broadcast(lecture_id, {
            "type":       "translation_error",
            "lecture_id": lecture_id,
            "timestamp":  timestamp,
            "message":    "Translation temporarily unavailable",
        })


async def _handle_language_change(lecture_id: str, data: dict, websocket: WebSocket) -> None:
    """
    Store the new target language for this lecture session.
    Optionally retranslate the last transcript into the new language immediately.
    """
    raw_lang = data.get("target_language", "").lower().strip()

    if raw_lang not in VALID_LANGUAGES:
        await manager.send_personal(websocket, {
            "type":    "error",
            "message": f"Invalid language '{raw_lang}'. Allowed: english, hindi, hinglish.",
        })
        return

    state = session_store.set_language(lecture_id, raw_lang)
    logger.info("WS language_change lecture=%s → %s", lecture_id, raw_lang)

    # If there is a recent transcript, retranslate it into the new language immediately
    # so the student sees the panel refresh rather than waiting for the next chunk.
    if state.last_transcript:
        try:
            result = await translate(state)
            if result:
                session_store.set_translation(lecture_id, result["translated"])
                await manager.send_personal(websocket, {
                    "type":      "translation",
                    "lecture_id": lecture_id,
                    "timestamp":  state.last_timestamp,
                    "content":    result["translated"],
                    "metadata":  {"language": result["language"], "source": "language_change"},
                })
        except Exception as exc:
            logger.error("Retranslation on language change failed lecture=%s: %s", lecture_id, exc)


async def _handle_frame(lecture_id: str, data: dict) -> None:
    """Receive a video frame, run vision/OCR, persist event, broadcast results."""
    timestamp = data.get("timestamp", 0.0)
    frame_b64 = data.get("data", "")

    try:
        import base64
        from app.services.vision_service import process_frame
        from app.schemas.events import LectureEvent
        from app.database.database import get_db
        import app.services.event_service as event_svc

        frame_bytes = base64.b64decode(frame_b64)
        result = await asyncio.get_event_loop().run_in_executor(
            None, process_frame, frame_bytes
        )
        if not result.get("significant"):
            return

        ocr_text = result.get("ocr_text", "").strip()
        if not ocr_text:
            return

        event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=timestamp,
            type="board",
            source="ocr",
            content=ocr_text,
            metadata={"is_formula": result.get("is_formula", False)},
        )

        async for db in get_db():
            await event_svc.save_event(db, event)

        await manager.broadcast(lecture_id, {
            "type": "board_event",
            "lecture_id": lecture_id,
            "timestamp": timestamp,
            "content": ocr_text,
            "metadata": event.metadata,
        })

    except Exception as exc:
        logger.error("Frame handler error lecture=%s: %s", lecture_id, exc)


async def _handle_lecture_completed(lecture_id: str, data: dict) -> None:
    """Mark lecture complete, trigger notes generation (Phase 8)."""
    timestamp = data.get("timestamp", 0.0)

    try:
        from app.database.database import get_db
        import app.services.lecture_service as lecture_svc
        from app.schemas.events import LectureEvent
        import app.services.event_service as event_svc

        event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=timestamp,
            type="lecture_completed",
            source="frontend",
            content="",
            metadata={},
        )

        async for db in get_db():
            await event_svc.save_event(db, event)
            await lecture_svc.complete_lecture(db, lecture_id)

        await manager.broadcast(lecture_id, {
            "type": "lecture_completed",
            "lecture_id": lecture_id,
            "message": "Lecture ended. Generating notes…",
        })

        # Phase 8 hook (no-op until graph is wired)
        try:
            from app.graph.notes_graph import run_notes_graph
            asyncio.create_task(run_notes_graph(lecture_id))
        except ImportError:
            pass

    except Exception as exc:
        logger.error("Completion handler error lecture=%s: %s", lecture_id, exc)
        await manager.broadcast(lecture_id, {"type": "error", "message": f"Completion error: {exc}"})


async def _handle_question(lecture_id: str, data: dict, websocket: WebSocket) -> None:
    """Route a student question through the Q&A graph (Phase 9)."""
    question = data.get("content", "")

    try:
        from app.graph.qa_graph import run_qa_graph
        answer = await run_qa_graph(lecture_id, question)
        await manager.send_personal(websocket, {
            "type": "answer",
            "lecture_id": lecture_id,
            "content": answer,
        })
    except Exception as exc:
        await manager.send_personal(websocket, {
            "type": "answer",
            "lecture_id": lecture_id,
            "content": f"Q&A not yet active (Phase 9). Error: {exc}",
        })
