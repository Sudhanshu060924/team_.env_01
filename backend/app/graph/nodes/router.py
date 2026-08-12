"""
Important Event Detection Node — Phase 9

Scans an accumulated speech transcript chunk for:
  - Key definitions  ("X is defined as …", "… is called …")
  - Formulas / equations  (mathematical notation present in text)
  - Critical concepts  ("remember", "important", "key point", etc.)
  - Algorithm steps  ("first step", "base case", "recursive case")

Uses a fast Groq call with a small, bounded prompt.
Throttled via the session store; call only accumulated transcript since last run.

Public interface
---------------
    events = await detect_important_events(transcript, timestamp, lecture_id)

    events is a list of dicts:
    [
        {
            "content":    "Binary search time complexity is O(log n)",
            "is_formula": True,
        },
        ...
    ]
    Returns [] on failure / nothing found / no API key.
"""
from __future__ import annotations

import logging
from typing import List

from app.config import get_settings
from app.integrations.groq_service import get_groq_client
from app.integrations.groq_limiter import groq_chat_with_retry

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a lecture highlight extractor.

Scan the teacher's speech for IMPORTANT educational moments:
  - Key definitions (e.g. "Binary search is an algorithm that...")
  - Formulas or equations (e.g. "time complexity is O(log n)")
  - Critical warnings or rules (e.g. "never forget that...", "always remember")
  - Algorithm steps or base cases
  - Named theorems or laws

Output a JSON array.  Each element:
  {"content": "<the key fact/formula as a short standalone sentence>", "is_formula": <true|false>}

is_formula is true when the item contains mathematical notation (Big-O, fractions, Greek letters, etc.).

Return [] if nothing important is found.
Return ONLY the JSON array — no explanation, no markdown.\
"""

_USER_PROMPT = """\
TRANSCRIPT SEGMENT:
{transcript}

Extract important moments. Return JSON array only.\
"""


async def detect_important_events(
    transcript: str,
    timestamp: float,
    lecture_id: str,
) -> List[dict]:
    """
    Detect key definitions, formulas, and concepts in a transcript chunk.

    Returns a list of {"content": str, "is_formula": bool} dicts.
    Returns [] on any failure.  Never raises.
    """
    if not transcript.strip():
        return []

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        return []

    # Truncate accumulated transcript to MAX_EVENT_CONTEXT_CHARS.
    max_ctx = settings.MAX_EVENT_CONTEXT_CHARS
    transcript_ctx = transcript[-max_ctx:] if len(transcript) > max_ctx else transcript

    logger.info(
        "important_events: Groq important event detection requested lecture=%s ts=%.1f chars=%d",
        lecture_id, timestamp, len(transcript_ctx),
    )

    try:
        import json
        client = get_groq_client()
        response = await groq_chat_with_retry(
            client,
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": _USER_PROMPT.format(transcript=transcript_ctx)},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []

        events = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            events.append({
                "content":    content,
                "is_formula": bool(item.get("is_formula", False)),
            })

        logger.debug(
            "important_events: found %d events for lecture=%s ts=%.1f",
            len(events), lecture_id, timestamp,
        )
        return events

    except Exception as exc:
        logger.warning("important_events: detection failed: %s", exc)
        return []
