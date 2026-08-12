"""
Lecture Session Store — Phase 7

Holds runtime translation context for each active lecture in a plain dict.
No database, no Redis — just process memory.  Data is lost when the server
restarts (which is fine: it's live-session context only).

Usage
-----
    from app.services.lecture_session import session_store
    state = session_store.get_or_create(lecture_id)
    session_store.update(lecture_id, target_language="hindi")
    session_store.add_transcript(lecture_id, "Binary search halves the array.")
    session_store.delete(lecture_id)
"""
from __future__ import annotations

import logging
import time
from typing import Dict

from app.graph.state import LectureSessionState, MAX_RECENT_TRANSCRIPTS, MAX_TECHNICAL_TERMS

logger = logging.getLogger(__name__)


class LectureSessionStore:
    """Thread-safe-enough for asyncio (single-threaded event loop)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, LectureSessionState] = {}
        # Throttle timestamps: lecture_id → last call epoch (float)
        self._last_topic_detection: Dict[str, float] = {}
        self._last_event_detection: Dict[str, float] = {}
        # Accumulated new transcript since last event detection run
        self._event_pending_transcript: Dict[str, str] = {}
        # Last successfully translated text (for dedup)
        self._last_translated_text: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def get_or_create(self, lecture_id: str) -> LectureSessionState:
        if lecture_id not in self._sessions:
            self._sessions[lecture_id] = LectureSessionState(lecture_id=lecture_id)
            logger.debug("session_store: created session for lecture=%s", lecture_id)
        return self._sessions[lecture_id]

    def get(self, lecture_id: str) -> LectureSessionState | None:
        return self._sessions.get(lecture_id)

    def delete(self, lecture_id: str) -> None:
        self._sessions.pop(lecture_id, None)
        self._last_topic_detection.pop(lecture_id, None)
        self._last_event_detection.pop(lecture_id, None)
        self._event_pending_transcript.pop(lecture_id, None)
        self._last_translated_text.pop(lecture_id, None)

    # ------------------------------------------------------------------
    # Mutations — always return the updated state
    # ------------------------------------------------------------------

    def set_language(self, lecture_id: str, target_language: str) -> LectureSessionState:
        state = self.get_or_create(lecture_id)
        self._sessions[lecture_id] = state.model_copy(update={"target_language": target_language})
        return self._sessions[lecture_id]

    def add_transcript(
        self,
        lecture_id: str,
        transcript: str,
        timestamp: float = 0.0,
    ) -> LectureSessionState:
        """Append a transcript segment, keeping the window bounded."""
        state = self.get_or_create(lecture_id)
        recent = (state.recent_transcripts + [transcript])[-MAX_RECENT_TRANSCRIPTS:]
        self._sessions[lecture_id] = state.model_copy(update={
            "recent_transcripts": recent,
            "last_transcript": transcript,
            "last_timestamp": timestamp,
        })
        return self._sessions[lecture_id]

    def set_translation(self, lecture_id: str, translation: str) -> LectureSessionState:
        state = self.get_or_create(lecture_id)
        self._sessions[lecture_id] = state.model_copy(update={"previous_translation": translation})
        return self._sessions[lecture_id]

    def add_technical_term(self, lecture_id: str, term: str) -> LectureSessionState:
        state = self.get_or_create(lecture_id)
        terms = state.technical_terms
        if term not in terms:
            terms = (terms + [term])[-MAX_TECHNICAL_TERMS:]
        self._sessions[lecture_id] = state.model_copy(update={"technical_terms": terms})
        return self._sessions[lecture_id]

    def set_topic(
        self,
        lecture_id: str,
        topic: str = "",
        subtopic: str = "",
    ) -> LectureSessionState:
        state = self.get_or_create(lecture_id)
        self._sessions[lecture_id] = state.model_copy(update={
            "current_topic": topic,
            "current_subtopic": subtopic,
        })
        return self._sessions[lecture_id]


    # ------------------------------------------------------------------
    # Throttle helpers
    # ------------------------------------------------------------------

    def should_run_topic_detection(self, lecture_id: str, interval_seconds: int) -> bool:
        """Return True if enough time has passed since the last topic detection."""
        last = self._last_topic_detection.get(lecture_id, 0.0)
        return (time.monotonic() - last) >= interval_seconds

    def mark_topic_detection_ran(self, lecture_id: str) -> None:
        self._last_topic_detection[lecture_id] = time.monotonic()

    def should_run_event_detection(self, lecture_id: str, interval_seconds: int) -> bool:
        """Return True if enough time has passed since the last event detection."""
        last = self._last_event_detection.get(lecture_id, 0.0)
        return (time.monotonic() - last) >= interval_seconds

    def mark_event_detection_ran(self, lecture_id: str) -> None:
        self._last_event_detection[lecture_id] = time.monotonic()

    def append_event_pending_transcript(self, lecture_id: str, transcript: str) -> None:
        """Accumulate transcript text for the next event detection run."""
        existing = self._event_pending_transcript.get(lecture_id, "")
        sep = " " if existing else ""
        self._event_pending_transcript[lecture_id] = (existing + sep + transcript).strip()

    def pop_event_pending_transcript(self, lecture_id: str) -> str:
        """Return and clear the accumulated pending transcript."""
        text = self._event_pending_transcript.pop(lecture_id, "")
        return text

    # ------------------------------------------------------------------
    # Duplicate translation guard
    # ------------------------------------------------------------------

    def is_duplicate_translation(self, lecture_id: str, transcript: str) -> bool:
        """Return True if transcript is identical to the last translated text."""
        return self._last_translated_text.get(lecture_id, "") == transcript

    def set_last_translated_text(self, lecture_id: str, transcript: str) -> None:
        self._last_translated_text[lecture_id] = transcript


# Module-level singleton
session_store = LectureSessionStore()
