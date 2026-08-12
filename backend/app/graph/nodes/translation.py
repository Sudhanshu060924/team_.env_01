"""
Translation Agent — Phase 7

Translates a Whisper transcript into the student's chosen language
(English / Hindi / Hinglish) using the Groq LLM with bounded context.

Changes for rate-limit management
----------------------------------
- Bounded context: prompt is capped at MAX_TRANSLATION_CONTEXT_CHARS.
- Short-transcript guard: skips Groq for trivially small input.
- Retry on 429: delegated to groq_chat_with_retry().

Public interface
---------------
    result = await translate(state)

    result is a dict:
    {
        "translated": "Binary search mein hum search space ko half karte hain.",
        "language":   "hinglish",
    }
    or {} on failure (caller handles gracefully).
"""
from __future__ import annotations

import logging
from typing import Literal

from app.graph.state import LectureSessionState, VALID_LANGUAGES
from app.integrations.groq_service import get_groq_client
from app.integrations.groq_limiter import groq_chat_with_retry
from app.config import get_settings

logger = logging.getLogger(__name__)

TargetLanguage = Literal["english", "hindi", "hinglish"]

# ── System prompt template ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a lecture translation assistant helping students follow a live class.

Your job is to translate the teacher's latest speech into {target_language_label}.

RULES:
- Translate accurately. Do NOT summarize, explain, or add information.
- Do NOT repeat yourself if the same content was in the previous translation.
- Preserve ALL technical terms, formulas, code, mathematical notation, numbers, and names EXACTLY.
- Use the recent lecture context to resolve pronouns (e.g. "it", "this").
- Return ONLY the translated text — no labels, no quotes, no explanation.

TARGET LANGUAGE INSTRUCTIONS:

English:
  Return natural, clear English.
  If the source is already English, return it as-is (minor cleanup is fine).

Hindi:
  Translate into natural spoken/educational Hindi (Devanagari script).
  Keep technical terms in English where they are normally used that way
  (e.g. "Binary Search", "Time Complexity", "O(log n)").
  Example: "Binary search search space को आधे में divide करता है।"

Hinglish:
  Write natural Indian Hinglish in Roman script ONLY. Do NOT use Devanagari.
  Mix Hindi and English naturally as an Indian student would speak.
  Example: "Binary search mein hum search space ko har step par half kar dete hain."\
"""

_USER_PROMPT = """\
LECTURE CONTEXT:
Topic: {topic}
Subtopic: {subtopic}
Technical terms seen so far: {terms}

RECENT TRANSCRIPT (last few segments):
{recent}

PREVIOUS TRANSLATION (for continuity):
{prev_translation}

LATEST TRANSCRIPT TO TRANSLATE:
{transcript}

Translate the LATEST TRANSCRIPT into {target_language_label}.\
"""

# ── Language display labels ───────────────────────────────────────────────────

_LABELS: dict[str, str] = {
    "english":  "English",
    "hindi":    "Hindi",
    "hinglish": "Hinglish",
}

# Filler words that are not worth translating on their own.
_FILLER_WORDS = frozenset({
    "um", "uh", "okay", "ok", "yes", "no", "so", "well", "right",
    "alright", "hmm", "ah", "err", "like",
})


def _is_trivial(text: str) -> bool:
    """Return True for empty / whitespace-only / filler-word-only text."""
    stripped = text.strip()
    if not stripped:
        return True
    words = stripped.lower().split()
    return all(w in _FILLER_WORDS for w in words)


def _truncate_to_chars(text: str, max_chars: int) -> str:
    """Truncate text to at most max_chars, preferring sentence boundaries."""
    if len(text) <= max_chars:
        return text
    # Try to cut at the last full sentence within budget.
    trimmed = text[-max_chars:]
    dot = trimmed.find(". ")
    if dot != -1:
        return trimmed[dot + 2:]
    return trimmed


# ── Main entry point ──────────────────────────────────────────────────────────

async def translate(state: LectureSessionState) -> dict:
    """
    Call the Groq LLM to translate state.last_transcript.

    Returns {"translated": str, "language": str} or {} on failure.
    Never raises — errors are logged and swallowed so transcription is unaffected.
    """
    transcript = state.last_transcript
    if _is_trivial(transcript):
        return {}

    lang = state.target_language.lower()
    if lang not in VALID_LANGUAGES:
        logger.warning("translation_agent: unknown target_language=%s — skipping", lang)
        return {}

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        logger.warning("translation_agent: GROQ_API_KEY not set — skipping translation")
        return {}

    # Hard length guard: reject transcripts below minimum threshold.
    if len(transcript.strip()) < settings.MIN_TRANSCRIPT_CHARS:
        logger.debug(
            "translation_agent: transcript too short (%d chars) — skipping",
            len(transcript.strip()),
        )
        return {}

    label = _LABELS[lang]

    # Build bounded context (capped at MAX_TRANSLATION_CONTEXT_CHARS total).
    max_ctx = settings.MAX_TRANSLATION_CONTEXT_CHARS

    # Recent transcripts: last 3 chunks only, then truncate the joined string.
    recent_chunks = state.recent_transcripts[-4:-1]  # up to 3 before current
    recent_raw = "\n".join(f"- {t}" for t in recent_chunks) or "(none yet)"
    recent_ctx = _truncate_to_chars(recent_raw, max_ctx // 4)

    terms_raw = ", ".join(state.technical_terms[:10]) if state.technical_terms else "(none detected)"
    prev_ctx  = _truncate_to_chars(state.previous_translation or "(none)", max_ctx // 8)

    system_msg = _SYSTEM_PROMPT.format(target_language_label=label)
    user_msg   = _USER_PROMPT.format(
        topic                 = state.current_topic    or "unknown",
        subtopic              = state.current_subtopic or "unknown",
        terms                 = terms_raw,
        recent                = recent_ctx,
        prev_translation      = prev_ctx,
        transcript            = transcript,
        target_language_label = label,
    )

    # Final safety: cap the entire user message.
    user_msg = _truncate_to_chars(user_msg, max_ctx)

    logger.info(
        "translation_agent: Groq translation requested lecture=%s lang=%s chars=%d",
        state.lecture_id, lang, len(transcript),
    )

    try:
        client = get_groq_client()
        response = await groq_chat_with_retry(
            client,
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        translated = response.choices[0].message.content.strip()
        if not translated:
            return {}

        logger.debug(
            "translation_agent: translated %d chars → %d chars (lang=%s)",
            len(transcript), len(translated), lang,
        )
        return {"translated": translated, "language": lang}

    except Exception as exc:
        logger.error("translation_agent: translation failed: %s", exc, exc_info=True)
        return {}
