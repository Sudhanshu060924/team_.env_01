"""
Phase 9 — Lecture-scoped AI Chatbot Service.

Responsibilities
----------------
1. Retrieve bounded lecture context (transcript chunks, notes, topics, important events).
2. Classify the student question against the lecture's known topics.
3. Generate a grounded answer using Groq LLM.
4. Persist the student question message + the AI reply message.
5. Return both messages for the chat response.

The AI reply message uses sender_role="ai" and stores:
  - detected_topic — topic from the lecture's existing topic list (or "Other")
  - ai_answer — the generated answer text (same as content)

Topic detection tries (in order):
  1. Exact match against known lecture topics (case-insensitive).
  2. LLM classification against the known topic list.
  3. "Other" if nothing matches.

This keeps teacher analytics clean by tying every question
to an existing topic emitted by the lecture Topic Agent.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database.models import (
    ChatMessage,
    ChatThread,
    Lecture,
    LectureEventModel,
)
from app.integrations.groq_service import get_groq_client
from app.integrations.groq_limiter import groq_chat_with_retry
from app.schemas.chat import ChatMessageRead


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

_MAX_TRANSCRIPT_CHARS = 3000
_MAX_NOTES_CHARS = 1500
_MAX_EVENTS_CHARS = 800

_MAX_ANSWER_TOKENS = 512
_MAX_TOPIC_TOKENS = 64


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _msg_to_read(msg: ChatMessage) -> ChatMessageRead:
    """
    Convert database ChatMessage model to API schema.
    """

    return ChatMessageRead(
        id=msg.id,
        thread_id=msg.thread_id,
        sender_id=msg.sender_id,
        sender_role=msg.sender_role,
        content=msg.content,
        created_at=msg.created_at,
        detected_topic=msg.detected_topic,
        ai_answer=msg.ai_answer,
    )


# ---------------------------------------------------------------------------
# Chat thread
# ---------------------------------------------------------------------------


async def _get_or_create_thread(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
) -> ChatThread:
    """
    Get the student's chat thread for this lecture.

    One student gets one private thread per lecture.
    """

    stmt = (
        select(ChatThread)
        .where(
            ChatThread.lecture_id == lecture_id,
            ChatThread.student_id == student_id,
        )
        .options(
            selectinload(ChatThread.messages),
            selectinload(ChatThread.student),
        )
    )

    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if thread is None:
        thread = ChatThread(
            lecture_id=lecture_id,
            student_id=student_id,
        )

        db.add(thread)

        await db.flush()
        await db.refresh(thread)

        result2 = await db.execute(stmt)
        thread = result2.scalar_one()

    return thread


# ---------------------------------------------------------------------------
# Lecture topics
# ---------------------------------------------------------------------------


async def _get_lecture_topics(
    db: AsyncSession,
    lecture_id: str,
) -> List[str]:
    """
    Return unique topic names from topic_update events.

    Topics are returned in the order in which they first appeared
    in the lecture timeline.

    IMPORTANT:
    Do not use:

        SELECT DISTINCT content
        ORDER BY timestamp

    because PostgreSQL rejects that query when timestamp is not
    part of the SELECT list.

    Instead, fetch content + timestamp and perform deduplication
    in Python.
    """

    result = await db.execute(
        select(
            LectureEventModel.content,
            LectureEventModel.timestamp,
        )
        .where(
            LectureEventModel.lecture_id == lecture_id,
            LectureEventModel.type == "topic_update",
        )
        .order_by(
            LectureEventModel.timestamp.asc()
        )
    )

    rows = result.all()

    topics: List[str] = []
    seen: set[str] = set()

    for content, timestamp in rows:
        topic = (content or "").strip()

        if not topic:
            continue

        # Case-insensitive duplicate detection.
        normalized = topic.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        topics.append(topic)

    logger.info(
        "chatbot: loaded %d topics for lecture=%s",
        len(topics),
        lecture_id,
    )

    return topics


# ---------------------------------------------------------------------------
# Lecture context
# ---------------------------------------------------------------------------


async def _get_lecture_context(
    db: AsyncSession,
    lecture_id: str,
    question: str,
) -> dict:
    """
    Retrieve bounded lecture content relevant to the question.

    Returns:

        {
            "transcript": str,
            "notes": str,
            "important_events": str,
            "topics": list[str],
        }
    """

    q_lower = question.lower()

    # -----------------------------------------------------------------------
    # Transcript
    # -----------------------------------------------------------------------

    result = await db.execute(
        select(LectureEventModel)
        .where(
            LectureEventModel.lecture_id == lecture_id,
            LectureEventModel.type.in_(
                [
                    "speech_event",
                    "speech",
                ]
            ),
        )
        .order_by(
            LectureEventModel.timestamp.asc()
        )
    )

    speech_events = result.scalars().all()

    # Score transcript chunks using simple keyword overlap.
    question_words = set(
        re.findall(
            r"\w+",
            q_lower,
        )
    )

    scored: list[tuple[float, str]] = []

    for ev in speech_events:
        text = (ev.content or "").strip()

        if not text:
            continue

        ev_lower = text.lower()

        overlap = sum(
            1
            for word in question_words
            if word in ev_lower
        )

        scored.append(
            (
                overlap,
                f"[{ev.timestamp:.0f}s] {text}",
            )
        )

    # Highest relevance first.
    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    transcript_lines: list[str] = []
    total = 0

    for _, line in scored:
        if total + len(line) > _MAX_TRANSCRIPT_CHARS:
            break

        transcript_lines.append(line)
        total += len(line)

    # Restore chronological order after relevance filtering.
    def _timestamp_from_line(line: str) -> float:
        match = re.match(
            r"\[(\d+(?:\.\d+)?)s\]",
            line,
        )

        if not match:
            return float("inf")

        return float(match.group(1))

    transcript_lines.sort(
        key=_timestamp_from_line
    )

    transcript_text = (
        "\n".join(transcript_lines)
        if transcript_lines
        else ""
    )

    # -----------------------------------------------------------------------
    # Notes
    # -----------------------------------------------------------------------

    from app.database.models import NoteModel

    result2 = await db.execute(
        select(NoteModel.content)
        .where(
            NoteModel.lecture_id == lecture_id,
            NoteModel.language == "english",
        )
        .order_by(
            NoteModel.created_at.desc()
        )
        .limit(1)
    )

    note_content = result2.scalar_one_or_none() or ""

    notes_text = note_content[:_MAX_NOTES_CHARS]

    # -----------------------------------------------------------------------
    # Important events
    # -----------------------------------------------------------------------

    result3 = await db.execute(
        select(LectureEventModel)
        .where(
            LectureEventModel.lecture_id == lecture_id,
            LectureEventModel.type == "important_event",
        )
        .order_by(
            LectureEventModel.timestamp.asc()
        )
    )

    imp_events = result3.scalars().all()

    imp_lines: list[str] = []
    total_imp = 0

    for ev in imp_events:
        line = (
            f"[{ev.timestamp:.0f}s] "
            f"{(ev.content or '').strip()}"
        )

        if total_imp + len(line) > _MAX_EVENTS_CHARS:
            break

        imp_lines.append(line)
        total_imp += len(line)

    events_text = "\n".join(imp_lines)

    # -----------------------------------------------------------------------
    # Topics
    # -----------------------------------------------------------------------

    topics = await _get_lecture_topics(
        db,
        lecture_id,
    )

    return {
        "transcript": transcript_text,
        "notes": notes_text,
        "important_events": events_text,
        "topics": topics,
    }


# ---------------------------------------------------------------------------
# Exact topic matching
# ---------------------------------------------------------------------------


def _exact_topic_match(
    question: str,
    topics: List[str],
) -> Optional[str]:
    """
    Return the first topic whose name appears in the question.

    Matching is case-insensitive.
    """

    q_lower = question.lower()

    for topic in topics:
        if topic.lower() in q_lower:
            return topic

    return None


# ---------------------------------------------------------------------------
# LLM topic classification
# ---------------------------------------------------------------------------


async def _llm_classify_topic(
    question: str,
    topics: List[str],
) -> str:
    """
    Ask Groq to select the best existing lecture topic.

    Never invent a new topic.
    """

    settings = get_settings()

    if not settings.GROQ_API_KEY:
        logger.warning(
            "chatbot: GROQ_API_KEY not configured"
        )
        return "Other"

    if not topics:
        return "Other"

    topic_list = "\n".join(
        f"- {topic}"
        for topic in topics
    )

    system = (
        "You are a topic classifier for educational lectures. "
        "Given a list of lecture topics and a student question, "
        "respond with a JSON object containing exactly one key "
        "'topic' whose value is the single most relevant topic "
        "from the list, or 'Other' if none match. "
        "Do not invent new topic names."
    )

    user = (
        f"LECTURE TOPICS:\n"
        f"{topic_list}\n\n"
        f"QUESTION:\n"
        f"{question}"
    )

    try:
        client = get_groq_client()

        response = await groq_chat_with_retry(
            client=client,
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": user,
                },
            ],
            temperature=0.0,
            max_tokens=_MAX_TOPIC_TOKENS,
        )

        raw = (
            response.choices[0]
            .message
            .content
            or ""
        ).strip()

        # ---------------------------------------------------------------
        # Try JSON response first.
        # ---------------------------------------------------------------

        try:
            data = json.loads(raw)

            detected = str(
                data.get(
                    "topic",
                    "Other",
                )
            ).strip()

        except (
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ):
            # -----------------------------------------------------------
            # Fallback to matching topic text in raw response.
            # -----------------------------------------------------------

            detected = "Other"

            for topic in topics:
                if topic.lower() in raw.lower():
                    detected = topic
                    break

        # ---------------------------------------------------------------
        # Verify model did not invent a topic.
        # ---------------------------------------------------------------

        topic_lookup = {
            topic.casefold(): topic
            for topic in topics
        }

        detected_normalized = detected.casefold()

        if detected_normalized in topic_lookup:
            return topic_lookup[detected_normalized]

        return "Other"

    except Exception as exc:
        logger.warning(
            "chatbot: topic classification failed: %s",
            exc,
            exc_info=True,
        )

        return "Other"


# ---------------------------------------------------------------------------
# Public topic detection
# ---------------------------------------------------------------------------


async def detect_topic(
    question: str,
    topics: List[str],
) -> str:
    """
    Classify question against known lecture topics.

    Order:
        1. exact match
        2. LLM classification
        3. Other
    """

    if not topics:
        return "Other"

    exact = _exact_topic_match(
        question,
        topics,
    )

    if exact:
        return exact

    return await _llm_classify_topic(
        question,
        topics,
    )


# ---------------------------------------------------------------------------
# Generate chatbot answer
# ---------------------------------------------------------------------------


async def generate_answer(
    question: str,
    context: dict,
    lecture_title: str,
) -> str:
    """
    Generate a grounded answer using lecture context.

    Returns the answer string.
    """

    settings = get_settings()

    if not settings.GROQ_API_KEY:
        return (
            "AI chatbot is not configured. "
            "Please contact your administrator."
        )

    has_context = bool(
        context.get("transcript")
        or context.get("notes")
        or context.get("important_events")
    )

    if not has_context:
        return (
            "This lecture does not have enough content yet "
            "to answer questions. Please check back once "
            "the lecture has been processed."
        )

    system = f"""
You are an AI study assistant for the lecture "{lecture_title}".

Your ONLY source of knowledge is the lecture content provided below.

Rules:
- Answer clearly and concisely.
- Base every statement on the lecture content.
- Preserve technical terms, formulas, and code exactly as they appear.
- If the lecture content does not contain enough information to answer
  the question, say:
  "The lecture does not cover this topic in enough detail to answer
  your question."
- Do NOT fabricate information.
- Do NOT reference external sources.
- Do NOT answer questions unrelated to this lecture.
"""

    context_parts: list[str] = []

    if context.get("transcript"):
        context_parts.append(
            "## LECTURE TRANSCRIPT (relevant excerpts)\n"
            f"{context['transcript']}"
        )

    if context.get("notes"):
        context_parts.append(
            "## LECTURE NOTES\n"
            f"{context['notes']}"
        )

    if context.get("important_events"):
        context_parts.append(
            "## IMPORTANT EVENTS\n"
            f"{context['important_events']}"
        )

    if context.get("topics"):
        context_parts.append(
            "## LECTURE TOPICS\n"
            + "\n".join(
                f"- {topic}"
                for topic in context["topics"]
            )
        )

    context_block = "\n\n".join(
        context_parts
    )

    user = (
        f"{context_block}\n\n"
        f"## STUDENT QUESTION\n"
        f"{question}"
    )

    try:
        client = get_groq_client()

        response = await groq_chat_with_retry(
            client=client,
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": user,
                },
            ],
            temperature=0.3,
            max_tokens=_MAX_ANSWER_TOKENS,
        )

        answer = (
            response.choices[0]
            .message
            .content
            or ""
        ).strip()

        if answer:
            return answer

        return (
            "I was unable to generate an answer. "
            "Please try again."
        )

    except Exception as exc:
        logger.error(
            "chatbot: answer generation failed "
            "for question=%r: %s",
            question,
            exc,
            exc_info=True,
        )

        return (
            "I encountered an error while generating "
            "an answer. Please try again."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ask_ai(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
    question: str,
) -> tuple[ChatMessageRead, ChatMessageRead]:
    """
    Handle a student AI chatbot question for a lecture.

    Flow:

        1. Verify lecture exists.
        2. Get/create student's thread.
        3. Retrieve lecture context.
        4. Detect topic.
        5. Generate answer.
        6. Persist student question.
        7. Persist AI answer.
        8. Return both messages.
    """

    # -----------------------------------------------------------------------
    # Validate question
    # -----------------------------------------------------------------------

    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty.",
        )

    # Optional safety limit.
    if len(question) > 2000:
        raise HTTPException(
            status_code=422,
            detail="Question is too long. Maximum length is 2000 characters.",
        )

    # -----------------------------------------------------------------------
    # Verify lecture exists
    # -----------------------------------------------------------------------

    result = await db.execute(
        select(Lecture).where(
            Lecture.id == lecture_id
        )
    )

    lecture = result.scalar_one_or_none()

    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail="Lecture not found",
        )

    # -----------------------------------------------------------------------
    # Get student's private thread
    # -----------------------------------------------------------------------

    thread = await _get_or_create_thread(
        db,
        lecture_id,
        student_id,
    )

    # -----------------------------------------------------------------------
    # Retrieve lecture context
    # -----------------------------------------------------------------------

    logger.info(
        "chatbot: retrieving context "
        "lecture=%s student=%s",
        lecture_id,
        student_id,
    )

    context = await _get_lecture_context(
        db,
        lecture_id,
        question,
    )

    # -----------------------------------------------------------------------
    # Detect topic
    # -----------------------------------------------------------------------

    topic = await detect_topic(
        question,
        context["topics"],
    )

    logger.info(
        "chatbot: topic detected "
        "lecture=%s topic=%s",
        lecture_id,
        topic,
    )

    # -----------------------------------------------------------------------
    # Generate answer
    # -----------------------------------------------------------------------

    answer = await generate_answer(
        question,
        context,
        lecture.title,
    )

    # -----------------------------------------------------------------------
    # Persist messages
    # -----------------------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    # Student message
    student_msg = ChatMessage(
        thread_id=thread.id,
        sender_id=student_id,
        sender_role="student",
        content=question,
        created_at=now,
    )

    db.add(student_msg)

    # AI message
    ai_msg = ChatMessage(
        thread_id=thread.id,
        sender_id=student_id,
        sender_role="ai",
        content=answer,
        detected_topic=topic,
        ai_answer=answer,
        created_at=now,
    )

    db.add(ai_msg)

    thread.updated_at = now

    await db.commit()

    await db.refresh(student_msg)
    await db.refresh(ai_msg)

    logger.info(
        "chatbot: response generated "
        "lecture=%s student=%s topic=%s",
        lecture_id,
        student_id,
        topic,
    )

    return (
        _msg_to_read(student_msg),
        _msg_to_read(ai_msg),
    )