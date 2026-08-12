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
from typing import Dict

from app.graph.state import LectureSessionState, MAX_RECENT_TRANSCRIPTS, MAX_TECHNICAL_TERMS

logger = logging.getLogger(__name__)


class LectureSessionStore:
    """Thread-safe-enough for asyncio (single-threaded event loop)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, LectureSessionState] = {}

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


# Module-level singleton
session_store = LectureSessionStore()
