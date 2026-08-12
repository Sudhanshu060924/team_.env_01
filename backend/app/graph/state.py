"""LangGraph shared state definitions — Phase 7."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# Valid student-facing translation targets
VALID_LANGUAGES = {"english", "hindi", "hinglish"}


class LectureSessionState(BaseModel):
    """
    Runtime state for one active lecture session.
    Kept in memory — NOT persisted to the database.

    This is the context window the Translation Agent reads on every chunk.
    """
    lecture_id: str = ""
    target_language: str = "english"         # "english" | "hindi" | "hinglish"

    # Bounded transcript history — last N speech segments
    recent_transcripts: List[str] = []       # capped at MAX_RECENT_TRANSCRIPTS

    # Extracted / inferred technical terms
    technical_terms: List[str] = []          # capped at MAX_TECHNICAL_TERMS

    # Current topic state
    current_topic: str = ""
    current_subtopic: str = ""

    # Last translation produced — forwarded as prior context
    previous_translation: str = ""

    # Last raw transcript — used for retranslation on language change
    last_transcript: str = ""
    last_timestamp: float = 0.0


# Context window sizes — keep prompt tokens manageable
MAX_RECENT_TRANSCRIPTS = 8
MAX_TECHNICAL_TERMS = 20


class GraphState(BaseModel):
    """LangGraph node I/O state (passed between graph nodes)."""
    lecture_id: str = ""
    transcript: str = ""
    translation: str = ""
    topic: str = ""
    notes: List[str] = []
    qa_answer: str = ""
    metadata: Dict[str, Any] = {}
