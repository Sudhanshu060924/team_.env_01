"""
Lecture Processing Pipeline — for pre-recorded Cloudinary videos.

Pipeline steps (run once per lecture):
  1. Download audio from Cloudinary video_url (via httpx streaming)
  2. Transcribe via Groq Whisper (verbose_json — returns per-segment timestamps)
  3. Group Whisper segments into ~5-second windows
  4. For each window (concurrently per chunk):
       a. Persist speech_event with real start/end timestamps
       b. Translate chunk via Gemini
       c. Detect topics from chunk
       d. Detect important events from chunk
  5. After all chunks processed → generate notes ONCE from full transcript
  6. Mark lecture as completed and broadcast done

Idempotency is enforced by the ProcessingRegistry (one task per lecture_id).

Event types stored in DB to match what the frontend queries:
  - "speech_event"    (transcript chunk, metadata contains start+end)
  - "translation"     (translated chunk, timestamp = chunk.start)
  - "topic_update"    (topic detection, timestamp = chunk.start)
  - "important_event" (key moment, timestamp = chunk.start)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import List

logger = logging.getLogger(__name__)

# Window size for grouping Whisper segments
_WINDOW_SECONDS = 5.0

# Maximum video duration to download (seconds) — protect against enormous files.
_MAX_DOWNLOAD_SECONDS = 7200  # 2 hours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_segments_into_windows(segments: list, window_size: float = _WINDOW_SECONDS) -> list:
    """
    Group Whisper segments into approximately window_size-second windows.

    Each window is a dict:
      { "start": float, "end": float, "text": str }

    Segments that already have an "end" key will use it; otherwise the start of
    the next segment is used as the end, and for the last segment we add 3s.
    """
    if not segments:
        return []

    # Normalise segments: ensure each has start, end, text
    normalised = []
    for i, seg in enumerate(segments):
        start = float(seg.get("start", 0.0))
        # Use explicit end if present, else derive from next segment's start
        if "end" in seg:
            end = float(seg["end"])
        elif i + 1 < len(segments):
            end = float(segments[i + 1].get("start", start + 3.0))
        else:
            end = start + 3.0
        text = (seg.get("text") or "").strip()
        if text:
            normalised.append({"start": start, "end": end, "text": text})

    if not normalised:
        return []

    # Group into windows
    windows = []
    window_start = normalised[0]["start"]
    window_end = window_start + window_size
    current_texts: list[str] = []
    current_end = window_start

    for seg in normalised:
        # If this segment starts a new window boundary, flush the current window
        if seg["start"] >= window_end and current_texts:
            windows.append({
                "start": window_start,
                "end": current_end,
                "text": " ".join(current_texts),
            })
            window_start = seg["start"]
            window_end = window_start + window_size
            current_texts = []

        current_texts.append(seg["text"])
        current_end = max(current_end, seg["end"])

    # Flush the last window
    if current_texts:
        windows.append({
            "start": window_start,
            "end": current_end,
            "text": " ".join(current_texts),
        })

    return windows


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_lecture_pipeline(lecture_id: str, video_url: str) -> None:
    """
    Full async processing pipeline for a pre-recorded lecture.

    This is meant to run as a background asyncio.Task.
    All exceptions are caught so the task never silently crashes without a log.
    """
    logger.info("Starting lecture processing lecture_id=%s", lecture_id)

    from app.services.websocket_manager import manager
    from app.services.lecture_session import session_store
    from app.database.database import get_db
    import app.services.event_service as event_svc
    import app.services.lecture_service as lecture_svc

    async def _broadcast(msg: dict) -> None:
        await manager.broadcast(lecture_id, msg)

    # ── 1. Download audio from Cloudinary ─────────────────────────────────
    logger.info("Downloading video audio lecture_id=%s url=%s", lecture_id, video_url)
    await _broadcast({
        "type": "processing_status",
        "lecture_id": lecture_id,
        "stage": "downloading",
        "message": "Downloading lecture video…",
    })

    try:
        audio_bytes, content_type = await _download_video(video_url)
    except Exception as exc:
        logger.error(
            "Download failed lecture_id=%s: %s", lecture_id, exc, exc_info=True
        )
        await _broadcast({
            "type": "processing_error",
            "lecture_id": lecture_id,
            "stage": "download",
            "message": f"Failed to download video: {exc}",
        })
        return

    if not audio_bytes:
        logger.error("Downloaded empty audio for lecture_id=%s", lecture_id)
        await _broadcast({
            "type": "processing_error",
            "lecture_id": lecture_id,
            "stage": "download",
            "message": "Downloaded video was empty.",
        })
        return

    logger.info(
        "Download complete lecture_id=%s bytes=%d", lecture_id, len(audio_bytes)
    )

    # ── 2. Transcription ───────────────────────────────────────────────────
    logger.info("Transcription started lecture_id=%s", lecture_id)
    await _broadcast({
        "type": "processing_status",
        "lecture_id": lecture_id,
        "stage": "transcribing",
        "message": "Transcribing audio…",
    })

    filename = _filename_from_url(video_url)

    try:
        from app.services.speech_service import transcribe_audio
        result = await transcribe_audio(audio_bytes, filename=filename)
    except Exception as exc:
        logger.error(
            "Transcription failed lecture_id=%s: %s", lecture_id, exc, exc_info=True
        )
        await _broadcast({
            "type": "processing_error",
            "lecture_id": lecture_id,
            "stage": "transcription",
            "message": f"Transcription failed: {exc}",
        })
        return

    transcript_text = (result.get("text") or "").strip()
    if not transcript_text:
        logger.warning("Empty transcription result for lecture_id=%s", lecture_id)
        await _broadcast({
            "type": "processing_status",
            "lecture_id": lecture_id,
            "stage": "transcription_empty",
            "message": "No speech detected in the video.",
        })
        await _run_notes_step(lecture_id)
        await _mark_completed(lecture_id)
        return

    raw_segments = result.get("segments") or []
    detected_lang = result.get("language", "en")

    logger.info(
        "Transcription completed lecture_id=%s chars=%d raw_segments=%d",
        lecture_id,
        len(transcript_text),
        len(raw_segments),
    )

    # ── 3. Group into ~5-second windows ───────────────────────────────────
    if raw_segments:
        windows = _group_segments_into_windows(raw_segments, _WINDOW_SECONDS)
    else:
        # No segment data — treat the whole transcript as one window
        windows = [{"start": 0.0, "end": 0.0, "text": transcript_text}]

    logger.info(
        "Transcript windowed lecture_id=%s windows=%d",
        lecture_id,
        len(windows),
    )

    # ── 4. Process each window incrementally ──────────────────────────────
    await _broadcast({
        "type": "processing_status",
        "lecture_id": lecture_id,
        "stage": "processing",
        "message": "Processing transcript chunks…",
    })

    from app.schemas.events import LectureEvent

    for window in windows:
        chunk_start: float = window["start"]
        chunk_end: float = window["end"]
        chunk_text: str = window["text"]

        logger.info(
            "Processing chunk lecture_id=%s start=%.1f end=%.1f chars=%d",
            lecture_id,
            chunk_start,
            chunk_end,
            len(chunk_text),
        )

        # ── 4a. Persist speech_event ─────────────────────────────────────
        seg_event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=chunk_start,
            type="speech_event",
            source="whisper",
            content=chunk_text,
            metadata={
                "start": chunk_start,
                "end": chunk_end,
                "language": detected_lang,
            },
        )
        async for db in get_db():
            await event_svc.save_event(db, seg_event)

        # Broadcast transcript chunk to frontend immediately
        await _broadcast({
            "type": "transcript",
            "lecture_id": lecture_id,
            "timestamp": chunk_start,
            "start": chunk_start,
            "end": chunk_end,
            "content": chunk_text,
            "metadata": {
                "start": chunk_start,
                "end": chunk_end,
                "language": detected_lang,
            },
        })

        # Update session store with this chunk for downstream agents
        session_store.add_transcript(lecture_id, chunk_text, timestamp=chunk_start)
        session_store.append_event_pending_transcript(lecture_id, chunk_text)

        # ── 4b-d. Run translation, topic, and event detection concurrently
        await asyncio.gather(
            _process_translation(lecture_id, chunk_text, chunk_start, chunk_end),
            _process_topic(lecture_id, chunk_start, chunk_end),
            _process_important_events(lecture_id, chunk_text, chunk_start, chunk_end),
            return_exceptions=True,  # one failure must not block others
        )

    # ── 5. Generate notes ONCE from the complete transcript ────────────────
    logger.info("Full transcript assembled lecture_id=%s — starting notes generation", lecture_id)
    await _run_notes_step(lecture_id)

    # ── 6. Mark lecture as completed and broadcast done ────────────────────
    await _mark_completed(lecture_id)


# ---------------------------------------------------------------------------
# Per-chunk processors
# ---------------------------------------------------------------------------

async def _process_translation(
    lecture_id: str,
    chunk_text: str,
    chunk_start: float,
    chunk_end: float,
) -> None:
    """Translate one chunk and persist + broadcast the result."""
    from app.services.websocket_manager import manager
    from app.services.lecture_session import session_store
    from app.graph.nodes.translation import translate
    from app.schemas.events import LectureEvent
    from app.database.database import get_db
    import app.services.event_service as event_svc

    try:
        state = session_store.get_or_create(lecture_id)
        result = await translate(state)
        if not result:
            logger.debug(
                "Translation skipped (trivial/short) lecture_id=%s start=%.1f",
                lecture_id, chunk_start,
            )
            return

        translated_text = result["translated"]
        translated_lang = result["language"]

        logger.info(
            "Translation chunk lecture_id=%s start=%.1f end=%.1f language=%s model=gemini",
            lecture_id, chunk_start, chunk_end, translated_lang,
        )

        # Persist translation event with real timestamps
        translation_event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=chunk_start,
            type="translation",
            source="translation_agent",
            content=translated_text,
            metadata={
                "start": chunk_start,
                "end": chunk_end,
                "language": translated_lang,
            },
        )
        async for db in get_db():
            await event_svc.save_event(db, translation_event)

        session_store.set_translation(lecture_id, translated_text)

        # Broadcast translation chunk
        await manager.broadcast(lecture_id, {
            "type": "translation",
            "lecture_id": lecture_id,
            "timestamp": chunk_start,
            "start": chunk_start,
            "end": chunk_end,
            "language": translated_lang,
            "content": translated_text,
            "metadata": {
                "start": chunk_start,
                "end": chunk_end,
                "language": translated_lang,
            },
        })

    except Exception as exc:
        logger.error(
            "Translation chunk failed lecture_id=%s start=%.1f: %s",
            lecture_id, chunk_start, exc, exc_info=True,
        )
        # Non-fatal — continue with other chunks


async def _process_topic(
    lecture_id: str,
    chunk_start: float,
    chunk_end: float,
) -> None:
    """Detect topic from current session state and persist + broadcast if changed."""
    from app.services.websocket_manager import manager
    from app.services.lecture_session import session_store
    from app.graph.nodes.supervisor import detect_topic
    from app.schemas.events import LectureEvent
    from app.database.database import get_db
    import app.services.event_service as event_svc

    try:
        state = session_store.get_or_create(lecture_id)
        result = await detect_topic(state)
        if not result or not result.get("changed"):
            return

        topic = result["topic"]
        subtopic = result["subtopic"]

        logger.info(
            "Topic detected lecture_id=%s timestamp=%.1f topic=%r",
            lecture_id, chunk_start, topic,
        )

        session_store.set_topic(lecture_id, topic=topic, subtopic=subtopic)

        topic_event = LectureEvent(
            event_id=str(uuid.uuid4()),
            lecture_id=lecture_id,
            timestamp=chunk_start,
            type="topic_update",
            source="topic_detector",
            content=topic,
            metadata={
                "start": chunk_start,
                "end": chunk_end,
                "subtopic": subtopic,
            },
        )
        async for db in get_db():
            await event_svc.save_event(db, topic_event)

        await manager.broadcast(lecture_id, {
            "type": "topic_update",
            "lecture_id": lecture_id,
            "timestamp": chunk_start,
            "start": chunk_start,
            "end": chunk_end,
            "content": topic,
            "metadata": {
                "start": chunk_start,
                "end": chunk_end,
                "subtopic": subtopic,
            },
        })

    except Exception as exc:
        logger.error(
            "Topic detection chunk failed lecture_id=%s start=%.1f: %s",
            lecture_id, chunk_start, exc, exc_info=True,
        )


async def _process_important_events(
    lecture_id: str,
    chunk_text: str,
    chunk_start: float,
    chunk_end: float,
) -> None:
    """Detect important events from a chunk and persist + broadcast each."""
    from app.services.websocket_manager import manager
    from app.graph.nodes.router import detect_important_events
    from app.schemas.events import LectureEvent
    from app.database.database import get_db
    import app.services.event_service as event_svc

    try:
        events = await detect_important_events(chunk_text, chunk_start, lecture_id)
        for evt in events:
            logger.info(
                "Important event lecture_id=%s timestamp=%.1f content=%r",
                lecture_id, chunk_start, evt["content"][:60],
            )

            ie_event = LectureEvent(
                event_id=str(uuid.uuid4()),
                lecture_id=lecture_id,
                timestamp=chunk_start,
                type="important_event",
                source="event_detector",
                content=evt["content"],
                metadata={
                    "start": chunk_start,
                    "end": chunk_end,
                    "is_formula": evt["is_formula"],
                },
            )
            async for db in get_db():
                await event_svc.save_event(db, ie_event)

            await manager.broadcast(lecture_id, {
                "type": "important_event",
                "lecture_id": lecture_id,
                "timestamp": chunk_start,
                "start": chunk_start,
                "end": chunk_end,
                "content": evt["content"],
                "metadata": {
                    "start": chunk_start,
                    "end": chunk_end,
                    "is_formula": evt["is_formula"],
                },
            })

    except Exception as exc:
        logger.error(
            "Important event detection chunk failed lecture_id=%s start=%.1f: %s",
            lecture_id, chunk_start, exc, exc_info=True,
        )


# ---------------------------------------------------------------------------
# Notes + completion helpers
# ---------------------------------------------------------------------------

async def _run_notes_step(lecture_id: str) -> None:
    """Generate notes ONCE from the full transcript. Non-fatal on failure."""
    logger.info("Notes generation started lecture_id=%s full transcript notes generation started", lecture_id)

    from app.services.websocket_manager import manager

    await manager.broadcast(lecture_id, {
        "type": "processing_status",
        "lecture_id": lecture_id,
        "stage": "notes",
        "message": "Generating notes…",
    })

    try:
        from app.graph.notes_graph import run_notes_graph
        await run_notes_graph(lecture_id)
        logger.info("Notes generation completed lecture_id=%s", lecture_id)
    except Exception as exc:
        logger.error(
            "Notes generation failed lecture_id=%s: %s",
            lecture_id,
            exc,
            exc_info=True,
        )
        await manager.broadcast(lecture_id, {
            "type": "processing_error",
            "lecture_id": lecture_id,
            "stage": "notes",
            "message": "Notes generation failed — transcript is still available.",
        })


async def _mark_completed(lecture_id: str) -> None:
    """Mark lecture as completed in DB and broadcast the completed event."""
    from app.services.websocket_manager import manager
    from app.database.database import get_db
    import app.services.lecture_service as lecture_svc

    try:
        async for db in get_db():
            await lecture_svc.complete_lecture(db, lecture_id)
    except Exception as exc:
        logger.error(
            "Failed to mark lecture completed lecture_id=%s: %s", lecture_id, exc
        )

    await manager.broadcast(lecture_id, {
        "type": "lecture_completed",
        "lecture_id": lecture_id,
        "message": "Lecture processing complete.",
    })

    logger.info("Lecture processing completed lecture_id=%s", lecture_id)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

async def _download_video(url: str) -> tuple[bytes, str]:
    """
    Download the video from a URL and return (raw_bytes, content_type).
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "video/mp4")
            return resp.content, content_type

    except ImportError:
        import urllib.request

        def _sync_download() -> tuple[bytes, str]:
            with urllib.request.urlopen(url, timeout=300) as resp:
                content_type = resp.headers.get("Content-Type", "video/mp4")
                return resp.read(), content_type

        return await asyncio.to_thread(_sync_download)


def _filename_from_url(url: str) -> str:
    """Extract a filename hint from a URL for audio format detection."""
    path = url.split("?")[0].split("/")[-1]
    if "." in path:
        return path
    return "video.mp4"
