"""
Supervisor / Topic Detection Node — Phase 9

Detects the current topic and subtopic from a rolling transcript window
using Groq LLM.  Throttled to at most once every TOPIC_DETECTION_INTERVAL_SECONDS
seconds to stay within Groq free-tier token limits.

Public interface
---------------
    result = await detect_topic(state)

    result is a dict:
    {
        "topic":    "Binary Search",
        "subtopic": "Time Complexity",
        "changed":  True,      # False when topic is unchanged
    }
    or {} on failure / no API key.
"""
from __future__ import annotations

import logging

from app.graph.state import LectureSessionState
from app.integrations.groq_service import get_groq_client
from app.integrations.groq_limiter import groq_chat_with_retry
from app.config import get_settings

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a lecture topic tracker.

Your job is to identify the CURRENT TOPIC and SUBTOPIC being taught based on
the teacher's recent speech.

Rules:
- Return ONLY a JSON object on a single line: {"topic": "...", "subtopic": "..."}
- topic: the main subject being taught right now (e.g. "Binary Search", "Recursion")
- subtopic: the specific aspect being covered (e.g. "Time Complexity", "Base Case")
         Leave subtopic empty string "" if none is identifiable.
- Keep both values short (under 6 words each).
- Do NOT add any explanation, markdown, or extra text.
- If you cannot determine a topic, return {"topic": "", "subtopic": ""}\
"""

_USER_PROMPT = """\
PREVIOUS TOPIC: {prev_topic}
PREVIOUS SUBTOPIC: {prev_subtopic}

RECENT TRANSCRIPT (oldest to newest):
{recent}

LATEST SEGMENT:
{transcript}

What is the current topic and subtopic? Return JSON only.\
"""


async def detect_topic(state: LectureSessionState) -> dict:
    """
    Identify the current lecture topic from the transcript context.

    Returns {"topic": str, "subtopic": str, "changed": bool} or {} on failure.
    Never raises.
    """
    if not state.last_transcript.strip():
        return {}

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        return {}

    max_ctx = settings.MAX_TOPIC_CONTEXT_CHARS

    # Bounded context: last 3 recent transcripts, capped to max_ctx chars.
    recent_chunks = state.recent_transcripts[-4:-1]  # up to 3 before current
    recent_raw = "\n".join(f"- {t}" for t in recent_chunks) or "(none yet)"
    if len(recent_raw) > max_ctx // 2:
        recent_raw = recent_raw[-(max_ctx // 2):]

    transcript_ctx = state.last_transcript[: max_ctx // 2]

    user_msg = _USER_PROMPT.format(
        prev_topic    = state.current_topic    or "(unknown)",
        prev_subtopic = state.current_subtopic or "(unknown)",
        recent        = recent_raw,
        transcript    = transcript_ctx,
    )

    logger.info(
        "topic_detector: Groq topic detection requested lecture=%s",
        state.lecture_id,
    )

    try:
        import json
        client = get_groq_client()
        response = await groq_chat_with_retry(
            client,
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=64,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        new_topic    = str(parsed.get("topic",    "")).strip()
        new_subtopic = str(parsed.get("subtopic", "")).strip()

        changed = (
            new_topic != state.current_topic or
            new_subtopic != state.current_subtopic
        ) and bool(new_topic)

        logger.debug(
            "topic_detector: topic=%r subtopic=%r changed=%s",
            new_topic, new_subtopic, changed,
        )
        return {"topic": new_topic, "subtopic": new_subtopic, "changed": changed}

    except Exception as exc:
        logger.warning("topic_detector: failed: %s", exc)
        return {}
