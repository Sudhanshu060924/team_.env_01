"""
Notes Generation Node — Phase 8

Takes the full transcript and board events from a completed lecture and
uses Groq LLM to produce structured study notes in Markdown.

The prompt instructs the model to:
  1. Identify the main topic and subtopics covered.
  2. Write a concise summary per section.
  3. Highlight any definitions, formulas, or key terms.
  4. Output clean Markdown with headings, bullets, and code blocks where appropriate.

Public interface
---------------
    from app.graph.nodes.notes import generate_notes

    markdown = await generate_notes(lecture_id, events)
"""
from __future__ import annotations

import logging
from typing import List

from app.schemas.events import LectureEvent
from app.config import get_settings
from app.integrations.groq_service import get_groq_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are VidyaRoom Notes Agent — an expert teaching assistant.
Your job is to read a raw lecture transcript and any board/slide text, then
produce clean, well-structured study notes in Markdown.

Rules:
- Use ## for main sections and ### for subsections.
- Use **bold** for key terms and definitions.
- Use LaTeX fenced code blocks (```math) for formulas.
- Include a short "Summary" section at the top (2-4 sentences).
- Include a "Key Takeaways" bullet list at the bottom (max 7 points).
- Be concise — omit filler words and repetition from the transcript.
- Preserve technical vocabulary exactly (do not paraphrase equations or algorithms).
- Write in English regardless of the source language.
"""


def _build_user_prompt(events: List[LectureEvent]) -> str:
    """Convert a list of LectureEvents into a structured prompt payload."""
    if not events:
        return "No transcript available."

    sections: list[str] = []
    speech_lines: list[str] = []
    board_lines:  list[str] = []

    for ev in events:
        if ev.type == "speech" and ev.content.strip():
            speech_lines.append(f"[{ev.timestamp:.1f}s] {ev.content.strip()}")
        elif ev.type in ("board", "ocr") and ev.content.strip():
            label = "FORMULA" if ev.metadata.get("is_formula") else "BOARD"
            board_lines.append(f"[{ev.timestamp:.1f}s] ({label}) {ev.content.strip()}")

    if speech_lines:
        sections.append("## TRANSCRIPT\n" + "\n".join(speech_lines))
    if board_lines:
        sections.append("## BOARD / SLIDES\n" + "\n".join(board_lines))

    return "\n\n".join(sections) if sections else "No transcript available."


async def generate_notes(lecture_id: str, events: List[LectureEvent]) -> str:
    """
    Call Groq LLM to produce Markdown study notes from the lecture events.

    Returns an empty string if:
    - No API key is configured.
    - There are no speech/board events to summarise.
    - The LLM call fails for any reason.
    """
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        logger.warning("Notes generation skipped: GROQ_API_KEY not set")
        return ""

    user_content = _build_user_prompt(events)
    if user_content == "No transcript available.":
        logger.info("Notes generation skipped: no usable events for lecture_id=%s", lecture_id)
        return ""

    try:
        client = get_groq_client()
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        notes_md = response.choices[0].message.content or ""
        logger.info(
            "Notes generated for lecture_id=%s — %d chars",
            lecture_id, len(notes_md),
        )
        return notes_md.strip()

    except Exception as exc:
        logger.error("Notes generation failed for lecture_id=%s: %s", lecture_id, exc, exc_info=True)
        return ""
