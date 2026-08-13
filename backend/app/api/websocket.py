"""
WebSocket endpoint: /ws/lectures/{lecture_id}

Message protocol (client → server):
  { "type": "audio_chunk",       "lecture_id": "...", "timestamp": 12.5, "data": "<base64>", "filename": "audio.webm" }
  { "type": "frame",             "lecture_id": "...", "timestamp": 14.0, "data": "<base64>" }
  { "type": "lecture_completed", "lecture_id": "...", "timestamp": 3600 }
  { "type": "language_change",   "lecture_id": "...", "target_language": "hinglish" }
  { "type": "question",          "lecture_id": "...", "content": "..." }
  { "type": "chat_message",      "thread_id": "...", "content": "..." }   ← student doubt
  { "type": "chat_reply",        "thread_id": "...", "content": "..." }   ← teacher reply
  { "type": "ping" }

Message protocol (server → client):
  { "type": "connected",              "lecture_id": "...", "message": "..." }
  { "type": "speech_event",           "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {...} }
  { "type": "translation",            "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {"language": "...", "source": "translation_agent"} }
  { "type": "translation_error",      "lecture_id": "...", "timestamp": ..., "message": "Translation temporarily unavailable" }
  { "type": "topic_update",           "lecture_id": "...", "timestamp": ..., "content": "...", "metadata": {...} }
  { "type": "important_event",        "lecture_id": "...", "timestamp": ..., "content": "..." }
  { "type": "notes",                  "lecture_id": "...", "content": "..." }
  { "type": "answer",                 "lecture_id": "...", "content": "..." }
  { "type": "chat_message_created",   "message": {...} }
  { "type": "error",                  "message": "..." }
  { "type": "pong" }
"""
import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.services.websocket_manager import manager
from app.graph.state import VALID_LANGUAGES
from app.services.lecture_session import session_store
from app.graph.nodes.translation import translate
from app.graph.nodes.supervisor import detect_topic
from app.graph.nodes.router import detect_important_events
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_user_from_token(token: Optional[str]):
    """
    Resolve a user from the session token passed as a query parameter.
    Returns the User ORM object, or None if the token is missing / invalid.
    Avoids touching the DB when no token is provided so unauthenticated
    viewers (live lecture observers) are unaffected.
    """
    if not token:
        return None
    try:
        from app.services.auth_service import get_user_id_from_session
        user_id = get_user_id_from_session(token)
        if not user_id:
            return None
        # Build a lightweight stand-in — we only need id and role for chat dispatch.
        # Full DB lookup happens in the per-message chat handlers which have their own db session.
        from types import SimpleNamespace
        return SimpleNamespace(id=user_id)
    except Exception:
        return None


@router.websocket("/ws/lectures/{lecture_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    lecture_id: str,
    token: Optional[str] = Query(default=None),
):
    # Resolve user (optional — existing live pipeline works without auth)
    caller = _resolve_user_from_token(token)
    user_id = caller.id if caller else None

    await manager.connect(lecture_id, websocket, user_id=user_id)

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

            # ── student requests notes in a specific language ──────────
            if msg_type == "generate_notes":
                asyncio.create_task(
                    _handle_generate_notes(lecture_id, data, websocket)
                )
                continue

            # ── student question via WebSocket ─────────────────────────
            if msg_type == "question":
                asyncio.create_task(
                    _handle_question(lecture_id, data, websocket)
                )
                continue

            # ── student sends a doubt message ──────────────────────────
            if msg_type == "chat_message":
                if not user_id:
                    await manager.send_personal(websocket, {
                        "type": "error",
                        "message": "Authentication required to send chat messages",
                    })
                    continue
                asyncio.create_task(
                    _handle_chat_message(lecture_id, user_id, data, websocket)
                )
                continue

            # ── teacher sends a reply ──────────────────────────────────
            if msg_type == "chat_reply":
                if not user_id:
                    await manager.send_personal(websocket, {
                        "type": "error",
                        "message": "Authentication required to send chat replies",
                    })
                    continue
                asyncio.create_task(
                    _handle_chat_reply(lecture_id, user_id, data, websocket)
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

        # Broadcast raw transcript to UI immediately — never blocked by Groq.
        await manager.broadcast(lecture_id, {
            "type": "speech_event",
            "lecture_id": lecture_id,
            "timestamp": timestamp,
            "content": text,
            "metadata": event.metadata,
        })

        # Accumulate transcript for throttled event detection.
        session_store.append_event_pending_transcript(lecture_id, text)

        # Priority 1: Translation (runs for each meaningful chunk).
        asyncio.create_task(
            _run_translation(lecture_id, text, timestamp)
        )

        # Priority 2: Topic detection (throttled).
        asyncio.create_task(
            _run_topic_detection(lecture_id, timestamp)
        )

        # Priority 3: Important event detection (throttled, uses accumulated text).
        asyncio.create_task(
            _run_important_event_detection(lecture_id, timestamp)
        )


    except Exception as exc:
        logger.error("Audio handler error lecture=%s: %s", lecture_id, exc, exc_info=True)
        await manager.broadcast(lecture_id, {"type": "error", "message": f"Speech error: {exc}"})


async def _run_translation(lecture_id: str, transcript: str, timestamp: float) -> None:
    """
    Update session context and call the Translation Agent.

    Guards:
      - Skips duplicate transcripts (identical to the last translated text).
      - Short/filler transcripts are dropped inside translate() itself.
    Runs as a separate task so it never blocks the next audio chunk.
    """
    try:
        # Dedup: skip if this exact text was already translated.
        if session_store.is_duplicate_translation(lecture_id, transcript):
            logger.debug(
                "translation_agent: duplicate transcript skipped lecture=%s", lecture_id
            )
            return

        # Update bounded context window.
        state = session_store.add_transcript(lecture_id, transcript, timestamp)

        result = await translate(state)
        if not result:
            # Translation returned nothing (short text, API key missing, etc.) — skip broadcast.
            return

        translated = result["translated"]
        lang       = result["language"]

        # Record translated text for dedup on next chunk.
        session_store.set_last_translated_text(lecture_id, transcript)
        # Persist the translation back into session for next-turn context.
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


async def _run_topic_detection(lecture_id: str, timestamp: float) -> None:
    """
    Run topic detection against the current session state.
    Throttled: skips if called within TOPIC_DETECTION_INTERVAL_SECONDS of last run.
    Broadcasts a 'topic_update' message if the topic changed.
    Runs as a separate task — never blocks the audio pipeline.
    """
    settings = get_settings()

    if not session_store.should_run_topic_detection(
        lecture_id, settings.TOPIC_DETECTION_INTERVAL_SECONDS
    ):
        logger.debug(
            "topic_detection: skipped due to throttle lecture=%s", lecture_id
        )
        return

    # Mark immediately so parallel tasks don't double-fire.
    session_store.mark_topic_detection_ran(lecture_id)

    try:
        state = session_store.get_or_create(lecture_id)
        result = await detect_topic(state)
        if not result or not result.get("changed"):
            return

        topic    = result["topic"]
        subtopic = result["subtopic"]

        # Update session state so translation context stays accurate.
        session_store.set_topic(lecture_id, topic=topic, subtopic=subtopic)

        await manager.broadcast(lecture_id, {
            "type":       "topic_update",
            "lecture_id": lecture_id,
            "timestamp":  timestamp,
            "content":    topic,
            "metadata":   {"subtopic": subtopic},
        })
        logger.info("topic_update broadcast lecture=%s topic=%r subtopic=%r", lecture_id, topic, subtopic)

    except Exception as exc:
        logger.error("Topic detection error lecture=%s: %s", lecture_id, exc, exc_info=True)


async def _run_important_event_detection(
    lecture_id: str,
    timestamp: float,
) -> None:
    """
    Detect key definitions, formulas, and concepts from accumulated transcript.
    Throttled: skips if called within IMPORTANT_EVENT_INTERVAL_SECONDS of last run.
    Only processes text accumulated since the previous run.
    Broadcasts one 'important_event' message per detected item.
    Runs as a separate task — never blocks the audio pipeline.
    """
    settings = get_settings()

    if not session_store.should_run_event_detection(
        lecture_id, settings.IMPORTANT_EVENT_INTERVAL_SECONDS
    ):
        logger.debug(
            "important_event_detection: skipped due to throttle lecture=%s", lecture_id
        )
        return

    # Pop accumulated transcript (cleared regardless of success/failure below).
    accumulated = session_store.pop_event_pending_transcript(lecture_id)
    if not accumulated.strip():
        return

    # Mark immediately so parallel tasks don't double-fire.
    session_store.mark_event_detection_ran(lecture_id)

    try:
        events = await detect_important_events(accumulated, timestamp, lecture_id)
        for evt in events:
            await manager.broadcast(lecture_id, {
                "type":       "important_event",
                "lecture_id": lecture_id,
                "timestamp":  timestamp,
                "content":    evt["content"],
                "metadata":   {"is_formula": evt["is_formula"]},
            })
    except Exception as exc:
        logger.error("Important event detection error lecture=%s: %s", lecture_id, exc, exc_info=True)




async def _handle_language_change(lecture_id: str, data: dict, websocket: WebSocket) -> None:
    """
    Store the new target language for this lecture session.

    Fetches all stored speech_event chunks from the DB and retranslates each
    one into the new language, preserving original timestamps.  This ensures
    the student sees a complete, timestamped translation panel immediately after
    switching language — without regenerating a single bulk summary.
    """
    raw_lang = data.get("target_language", "").lower().strip()

    if raw_lang not in VALID_LANGUAGES:
        await manager.send_personal(websocket, {
            "type":    "error",
            "message": f"Invalid language '{raw_lang}'. Allowed: english, hindi, hinglish.",
        })
        return

    session_store.set_language(lecture_id, raw_lang)
    logger.info("WS language_change lecture=%s → %s", lecture_id, raw_lang)

    # Fetch all speech_event chunks from DB and retranslate each one
    try:
        from app.database.database import get_db
        import app.services.event_service as event_svc
        import uuid as _uuid
        from app.schemas.events import LectureEvent as _LectureEvent

        speech_events = []
        async for db in get_db():
            speech_events = await event_svc.get_events(db, lecture_id, event_type="speech_event")

        if not speech_events:
            # No stored chunks — fall back to retranslating just the last transcript in session
            state = session_store.get_or_create(lecture_id)
            if state.last_transcript:
                result = await translate(state)
                if result:
                    session_store.set_translation(lecture_id, result["translated"])
                    await manager.send_personal(websocket, {
                        "type":       "translation",
                        "lecture_id": lecture_id,
                        "timestamp":  state.last_timestamp,
                        "start":      state.last_timestamp,
                        "end":        state.last_timestamp,
                        "language":   result["language"],
                        "content":    result["translated"],
                        "metadata":   {"language": result["language"], "source": "language_change"},
                    })
            return

        logger.info(
            "WS language_change: retranslating %d chunks lecture=%s lang=%s",
            len(speech_events), lecture_id, raw_lang,
        )

        for ev in speech_events:
            chunk_text = ev.content.strip()
            if not chunk_text:
                continue

            chunk_start = float(ev.metadata.get("start", ev.timestamp))
            chunk_end   = float(ev.metadata.get("end",   ev.timestamp))

            # Update session with this chunk so translate() has correct context
            state = session_store.add_transcript(lecture_id, chunk_text, timestamp=chunk_start)

            try:
                result = await translate(state)
            except Exception as exc:
                logger.error(
                    "language_change retranslation failed lecture=%s start=%.1f: %s",
                    lecture_id, chunk_start, exc,
                )
                continue

            if not result:
                continue

            translated   = result["translated"]
            trans_lang   = result["language"]

            session_store.set_translation(lecture_id, translated)

            # Persist a fresh translation event
            try:
                translation_event = _LectureEvent(
                    event_id=str(_uuid.uuid4()),
                    lecture_id=lecture_id,
                    timestamp=chunk_start,
                    type="translation",
                    source="language_change",
                    content=translated,
                    metadata={
                        "start":    chunk_start,
                        "end":      chunk_end,
                        "language": trans_lang,
                    },
                )
                async for db in get_db():
                    await event_svc.save_event(db, translation_event)
            except Exception as exc:
                logger.warning("Failed to persist retranslation lecture=%s: %s", lecture_id, exc)

            # Stream to the requesting student immediately
            await manager.send_personal(websocket, {
                "type":       "translation",
                "lecture_id": lecture_id,
                "timestamp":  chunk_start,
                "start":      chunk_start,
                "end":        chunk_end,
                "language":   trans_lang,
                "content":    translated,
                "metadata":   {
                    "start":    chunk_start,
                    "end":      chunk_end,
                    "language": trans_lang,
                    "source":   "language_change",
                },
            })

    except Exception as exc:
        logger.error("language_change handler failed lecture=%s: %s", lecture_id, exc, exc_info=True)


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


async def _handle_generate_notes(lecture_id: str, data: dict, websocket: WebSocket) -> None:
    """
    Regenerate notes for a completed lecture in a requested language.

    Client sends:
      { "type": "generate_notes", "lecture_id": "...", "target_language": "hindi" }

    The handler signals 'notes_generating' back to the requesting client,
    then runs the notes graph, which broadcasts the result to all clients.
    """
    raw_lang = data.get("target_language", "").lower().strip()

    if raw_lang not in VALID_LANGUAGES:
        await manager.send_personal(websocket, {
            "type":    "error",
            "message": f"Invalid language '{raw_lang}'. Allowed: english, hindi, hinglish.",
        })
        return

    # Acknowledge immediately so the UI can show a loading state
    await manager.send_personal(websocket, {
        "type":       "notes_generating",
        "lecture_id": lecture_id,
        "language":   raw_lang,
    })

    try:
        from app.graph.notes_graph import run_notes_graph
        asyncio.create_task(run_notes_graph(lecture_id, target_language=raw_lang))
    except Exception as exc:
        logger.error("generate_notes handler error lecture=%s: %s", lecture_id, exc)
        await manager.send_personal(websocket, {
            "type":    "error",
            "message": f"Notes generation failed: {exc}",
        })


# ---------------------------------------------------------------------------
# Chat handlers — Student ↔ Teacher live doubt system
# ---------------------------------------------------------------------------

async def _handle_chat_message(
    lecture_id: str,
    sender_user_id: str,
    data: dict,
    websocket: WebSocket,
) -> None:
    """
    Student sends a chat_message.

    Flow:
      1. Validate content
      2. Get the sender's user record + verify role=student
      3. Find/create thread for (lecture_id, student_id)
      4. Persist message in DB
      5. Echo saved message to the student
      6. Broadcast chat_message_created to ALL connections on this lecture
         (so teachers connected to the same lecture WS see it immediately)
    """
    content = (data.get("content") or "").strip()
    if not content:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "Message content must not be empty",
        })
        return
    if len(content) > 2000:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "Message must be at most 2000 characters",
        })
        return

    try:
        from app.database.database import get_db
        from app.database.models import User
        from sqlalchemy import select
        import app.services.chat_service as chat_svc

        async for db in get_db():
            # Verify sender is a student
            result = await db.execute(select(User).where(User.id == sender_user_id))
            user = result.scalar_one_or_none()
            if user is None or user.role != "student":
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Only students can send chat_message",
                })
                return

            msg_read = await chat_svc.post_student_message(
                db, lecture_id, sender_user_id, content
            )

        payload = {
            "type": "chat_message_created",
            "message": {
                "id": msg_read.id,
                "thread_id": msg_read.thread_id,
                "sender_id": msg_read.sender_id,
                "sender_role": msg_read.sender_role,
                "content": msg_read.content,
                "created_at": msg_read.created_at.isoformat(),
            },
        }
        # Echo to sender
        await manager.send_personal(websocket, payload)
        # Broadcast to all connected clients on this lecture (teachers see it)
        await manager.broadcast(lecture_id, payload)

    except Exception as exc:
        logger.error("chat_message handler error lecture=%s: %s", lecture_id, exc)
        await manager.send_personal(websocket, {
            "type": "error",
            "message": f"Failed to save message: {exc}",
        })


async def _handle_chat_reply(
    lecture_id: str,
    sender_user_id: str,
    data: dict,
    websocket: WebSocket,
) -> None:
    """
    Teacher sends a chat_reply.

    Flow:
      1. Validate content + thread_id
      2. Verify sender role=teacher
      3. Verify teacher owns the lecture (via chat_service)
      4. Persist reply in DB
      5. Echo saved message back to teacher
      6. Send reply directly to the student's WebSocket connection(s)
      7. Also broadcast to all lecture connections for completeness
    """
    thread_id = (data.get("thread_id") or "").strip()
    content = (data.get("content") or "").strip()

    if not thread_id:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "thread_id is required for chat_reply",
        })
        return
    if not content:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "Message content must not be empty",
        })
        return
    if len(content) > 2000:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "Message must be at most 2000 characters",
        })
        return

    try:
        from app.database.database import get_db
        from app.database.models import User, ChatThread
        from sqlalchemy import select
        import app.services.chat_service as chat_svc

        async for db in get_db():
            # Verify sender is a teacher
            result = await db.execute(select(User).where(User.id == sender_user_id))
            user = result.scalar_one_or_none()
            if user is None or user.role != "teacher":
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Only teachers can send chat_reply",
                })
                return

            msg_read = await chat_svc.post_teacher_reply(
                db, lecture_id, thread_id, sender_user_id, content
            )

            # Look up the thread's student_id to deliver reply to that student
            thread_result = await db.execute(
                select(ChatThread).where(ChatThread.id == thread_id)
            )
            thread = thread_result.scalar_one_or_none()
            student_id = thread.student_id if thread else None

        payload = {
            "type": "chat_message_created",
            "message": {
                "id": msg_read.id,
                "thread_id": msg_read.thread_id,
                "sender_id": msg_read.sender_id,
                "sender_role": msg_read.sender_role,
                "content": msg_read.content,
                "created_at": msg_read.created_at.isoformat(),
            },
        }
        # Echo to teacher
        await manager.send_personal(websocket, payload)
        # Deliver directly to the student if they are connected
        if student_id:
            await manager.send_to_user(student_id, payload)

    except Exception as exc:
        logger.error("chat_reply handler error lecture=%s: %s", lecture_id, exc)
        await manager.send_personal(websocket, {
            "type": "error",
            "message": f"Failed to save reply: {exc}",
        })
