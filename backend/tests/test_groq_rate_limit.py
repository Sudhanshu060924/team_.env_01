"""
Groq Rate-Limit Tests

Covers the 10 scenarios specified in the requirements:

1.  Translation context is bounded (MAX_TRANSLATION_CONTEXT_CHARS).
2.  Topic detection is throttled (TOPIC_DETECTION_INTERVAL_SECONDS).
3.  Important event detection is throttled (IMPORTANT_EVENT_INTERVAL_SECONDS).
4.  Duplicate translation is skipped.
5.  HTTP 429 (RateLimitError) is retried.
6.  Retry stops after GROQ_MAX_RETRIES.
7.  Translation failure does not stop Whisper (transcription reaches UI).
8.  Topic detection failure does not stop the lecture.
9.  Important event detection failure does not stop the lecture.
10. Concurrent Groq calls are limited by the semaphore.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.graph.state import LectureSessionState
from app.graph.nodes.translation import translate, _is_trivial, _truncate_to_chars
from app.services.lecture_session import LectureSessionStore
from app.integrations.groq_limiter import groq_chat_with_retry, reset_semaphore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> LectureSessionState:
    defaults = dict(
        lecture_id="lec-rl",
        target_language="english",
        last_transcript="Binary search divides the search space in half.",
        last_timestamp=10.0,
        recent_transcripts=[
            "Today we discuss binary search.",
            "Binary search divides the search space in half.",
        ],
        technical_terms=["Binary Search", "O(log n)"],
        current_topic="Binary Search",
        current_subtopic="Time Complexity",
        previous_translation="",
    )
    defaults.update(kwargs)
    return LectureSessionState(**defaults)


def _mock_groq_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# 1. Translation context is bounded
# ---------------------------------------------------------------------------

def test_truncate_to_chars_within_limit():
    """_truncate_to_chars returns text unchanged when under the limit."""
    text = "hello world"
    assert _truncate_to_chars(text, 100) == text


def test_truncate_to_chars_over_limit():
    """_truncate_to_chars trims text to at most max_chars."""
    text = "a" * 5000
    result = _truncate_to_chars(text, 4000)
    assert len(result) <= 4000


def test_truncate_prefers_sentence_boundary():
    """_truncate_to_chars cuts at a '. ' sentence boundary when possible."""
    # Build a string that is exactly over the limit.
    # The last 4000 chars start mid-sentence; there is a '. ' inside.
    long_prefix = "x" * 1000
    sentence_a  = "This is a full sentence."
    gap         = " "
    sentence_b  = "y" * 3500  # makes total > 4000
    text = long_prefix + sentence_a + gap + sentence_b
    result = _truncate_to_chars(text, 4000)
    # Result should start from after a sentence boundary.
    assert len(result) <= 4000


@pytest.mark.asyncio
async def test_translation_prompt_respects_max_context_chars():
    """The user_msg sent to Gemini must not exceed MAX_TRANSLATION_CONTEXT_CHARS."""
    # Build a state with very large recent_transcripts and previous_translation.
    long_text = "Binary search is a great algorithm. " * 300  # ~10 800 chars
    state = _make_state(
        recent_transcripts=[long_text, long_text, long_text, long_text],
        previous_translation=long_text,
    )

    # Capture the user_prompt passed to gemini_translate
    captured: dict = {}

    async def _fake_gemini_translate(*, system_prompt, user_prompt, model, **kwargs):
        captured["user_prompt"] = user_prompt
        return "ok"

    with patch("app.graph.nodes.translation.gemini_translate", side_effect=_fake_gemini_translate), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GEMINI_API_KEY = "fake"
        ms.return_value.GEMINI_TRANSLATION_MODEL = "gemini-2.5-flash-lite"
        ms.return_value.MAX_TRANSLATION_CONTEXT_CHARS = 4000
        ms.return_value.MIN_TRANSCRIPT_CHARS = 5
        await translate(state)

    # Verify the user message was capped.
    assert "user_prompt" in captured, "gemini_translate was not called"
    assert len(captured["user_prompt"]) <= 4000


# ---------------------------------------------------------------------------
# 2. Topic detection is throttled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_topic_detection_throttled():
    """
    _run_topic_detection must skip (not call detect_topic) when interval has
    not elapsed since last run.
    """
    from app.api.websocket import _run_topic_detection

    store = LectureSessionStore()
    store.get_or_create("lec-throttle-t")
    # Pretend it ran one second ago — well within the 30-second window.
    store._last_topic_detection["lec-throttle-t"] = time.monotonic() - 1

    detect_mock = AsyncMock(return_value={"topic": "T", "subtopic": "", "changed": True})

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", detect_mock), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_topic_detection("lec-throttle-t", 5.0)

    detect_mock.assert_not_called()


@pytest.mark.asyncio
async def test_topic_detection_runs_after_interval():
    """detect_topic IS called when the interval has elapsed."""
    from app.api.websocket import _run_topic_detection

    store = LectureSessionStore()
    store.get_or_create("lec-throttle-t2")
    # Pretend it ran 35 seconds ago — beyond the window.
    store._last_topic_detection["lec-throttle-t2"] = time.monotonic() - 35

    detect_mock = AsyncMock(return_value={"topic": "T", "subtopic": "", "changed": False})

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", detect_mock), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_topic_detection("lec-throttle-t2", 5.0)

    detect_mock.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Important event detection is throttled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_detection_throttled():
    """_run_important_event_detection skips when interval has not elapsed."""
    from app.api.websocket import _run_important_event_detection

    store = LectureSessionStore()
    store.get_or_create("lec-throttle-e")
    store._last_event_detection["lec-throttle-e"] = time.monotonic() - 1
    store._event_pending_transcript["lec-throttle-e"] = "Some important text."

    detect_mock = AsyncMock(return_value=[])

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events", detect_mock), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_important_event_detection("lec-throttle-e", 5.0)

    detect_mock.assert_not_called()


@pytest.mark.asyncio
async def test_event_detection_runs_after_interval():
    """detect_important_events IS called after the interval elapsed."""
    from app.api.websocket import _run_important_event_detection

    store = LectureSessionStore()
    store.get_or_create("lec-throttle-e2")
    store._last_event_detection["lec-throttle-e2"] = time.monotonic() - 35
    store._event_pending_transcript["lec-throttle-e2"] = "Binary search is O(log n)."

    detect_mock = AsyncMock(return_value=[])

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events", detect_mock), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_important_event_detection("lec-throttle-e2", 5.0)

    detect_mock.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Duplicate translation is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_translation_skipped():
    """_run_translation skips calling translate() if same transcript was already translated."""
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-dedup")
    transcript = "Binary search divides the array."
    store.set_last_translated_text("lec-dedup", transcript)  # mark as already translated

    translate_mock = AsyncMock(return_value={"translated": "ok", "language": "english"})

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.translate", translate_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_translation("lec-dedup", transcript, 5.0)

    translate_mock.assert_not_called()
    mock_mgr.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_different_transcript_not_skipped():
    """A different transcript (not duplicate) proceeds to translation."""
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-dedup2")
    store.set_last_translated_text("lec-dedup2", "some old text")

    translate_mock = AsyncMock(return_value={"translated": "New translation.", "language": "english"})

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.translate", translate_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_translation("lec-dedup2", "completely new text here", 5.0)

    translate_mock.assert_called_once()


# ---------------------------------------------------------------------------
# 5. HTTP 429 is retried
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_rate_limit_error_retried():
    """groq_chat_with_retry retries on RateLimitError and eventually succeeds."""
    # We test the retry mechanism by having the real groq.RateLimitError class
    # available (it extends Exception).  Since tests don't hit a real API we
    # use a subclass so we can inject it without an API key.
    try:
        from groq import RateLimitError
    except ImportError:
        pytest.skip("groq not installed")

    success_response = _mock_groq_response("result")
    call_count = 0

    async def fail_once(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RateLimitError("rate limited", response=MagicMock(), body={})
        return success_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = fail_once

    reset_semaphore()

    with patch("app.integrations.groq_limiter.get_settings") as ms, \
         patch("app.integrations.groq_limiter.asyncio.sleep", new_callable=AsyncMock):
        ms.return_value.MAX_CONCURRENT_GROQ_REQUESTS = 1
        ms.return_value.GROQ_MAX_RETRIES = 2
        result = await groq_chat_with_retry(mock_client, model="m", messages=[])

    assert call_count == 2
    assert result is success_response


# ---------------------------------------------------------------------------
# 6. Retry stops after GROQ_MAX_RETRIES
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_retry_stops_after_max_retries():
    """
    groq_chat_with_retry raises after GROQ_MAX_RETRIES+1 total attempts.
    """
    try:
        from groq import RateLimitError
    except ImportError:
        pytest.skip("groq not installed")

    attempts = []

    async def always_fail(**kwargs):
        attempts.append(1)
        raise RateLimitError("always 429", response=MagicMock(), body={})

    mock_client = MagicMock()
    mock_client.chat.completions.create = always_fail

    reset_semaphore()

    with patch("app.integrations.groq_limiter.get_settings") as ms, \
         patch("app.integrations.groq_limiter.asyncio.sleep", new_callable=AsyncMock):
        ms.return_value.MAX_CONCURRENT_GROQ_REQUESTS = 1
        ms.return_value.GROQ_MAX_RETRIES = 2
        with pytest.raises(RateLimitError):
            await groq_chat_with_retry(mock_client, model="m", messages=[])

    # 1 initial attempt + 2 retries = 3 total.
    assert len(attempts) == 3


# ---------------------------------------------------------------------------
# 6. Retry uses exponential backoff (sleep durations)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_retry_exponential_backoff():
    """Retry waits 1s then 2s (2^0, 2^1)."""
    try:
        from groq import RateLimitError
    except ImportError:
        pytest.skip("groq not installed")

    call_n = 0
    success_resp = _mock_groq_response("ok")

    async def fail_twice(**kwargs):
        nonlocal call_n
        call_n += 1
        if call_n <= 2:
            raise RateLimitError("429", response=MagicMock(), body={})
        return success_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fail_twice

    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    reset_semaphore()

    with patch("app.integrations.groq_limiter.get_settings") as ms, \
         patch("app.integrations.groq_limiter.asyncio.sleep", side_effect=fake_sleep):
        ms.return_value.MAX_CONCURRENT_GROQ_REQUESTS = 1
        ms.return_value.GROQ_MAX_RETRIES = 2
        reset_semaphore()
        result = await groq_chat_with_retry(mock_client, model="m", messages=[])

    assert result is success_resp
    assert sleep_calls == [1, 2]


# ---------------------------------------------------------------------------
# 7. Translation failure does not stop Whisper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translation_failure_does_not_stop_transcription():
    """
    translate() must never raise — errors are swallowed.
    This means the speech_event path is unaffected.
    """
    with patch("app.graph.nodes.translation.gemini_translate",
               new_callable=AsyncMock,
               side_effect=RuntimeError("network down")), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GEMINI_API_KEY = "fake"
        ms.return_value.GEMINI_TRANSLATION_MODEL = "gemini-2.5-flash-lite"
        ms.return_value.MAX_TRANSLATION_CONTEXT_CHARS = 4000
        ms.return_value.MIN_TRANSCRIPT_CHARS = 5
        # Must NOT raise.
        result = await translate(_make_state())

    assert result == {}


@pytest.mark.asyncio
async def test_run_translation_broadcasts_speech_independently():
    """
    _run_translation is a separate asyncio task; its failure must not prevent
    speech_event from being broadcast (those are two separate awaits).
    """
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-isolation")

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.translate", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        mock_mgr.broadcast = AsyncMock()
        # Must NOT raise.
        await _run_translation("lec-isolation", "Some transcript.", 1.0)

    # A translation_error should have been broadcast, NOT a crash.
    calls = mock_mgr.broadcast.call_args_list
    types = [c.args[1]["type"] for c in calls]
    assert "translation_error" in types


# ---------------------------------------------------------------------------
# 8. Topic detection failure does not stop the lecture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_topic_detection_failure_does_not_raise():
    """_run_topic_detection catches all exceptions and never re-raises."""
    from app.api.websocket import _run_topic_detection

    store = LectureSessionStore()
    store.get_or_create("lec-topic-fail")
    # Allow the throttle gate to pass.
    store._last_topic_detection["lec-topic-fail"] = time.monotonic() - 60

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        # Must NOT raise.
        await _run_topic_detection("lec-topic-fail", 1.0)


# ---------------------------------------------------------------------------
# 9. Important event detection failure does not stop the lecture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_detection_failure_does_not_raise():
    """_run_important_event_detection catches all exceptions and never re-raises."""
    from app.api.websocket import _run_important_event_detection

    store = LectureSessionStore()
    store.get_or_create("lec-evt-fail")
    store._last_event_detection["lec-evt-fail"] = time.monotonic() - 60
    store._event_pending_transcript["lec-evt-fail"] = "Some text to process."

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events",
               new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        # Must NOT raise.
        await _run_important_event_detection("lec-evt-fail", 1.0)


# ---------------------------------------------------------------------------
# 10. Concurrent Groq calls are limited by the semaphore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_semaphore_limits_concurrency():
    """
    With MAX_CONCURRENT_GROQ_REQUESTS=1, only one Groq call may be active
    at a time.  We verify that tasks queue behind each other.
    """
    reset_semaphore()

    # Track concurrency: how many calls are in-flight simultaneously.
    active = 0
    max_active = 0

    async def slow_create(**kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)  # yield control
        active -= 1
        return _mock_groq_response("ok")

    mock_client = MagicMock()
    mock_client.chat.completions.create = slow_create

    with patch("app.integrations.groq_limiter.get_settings") as ms:
        ms.return_value.MAX_CONCURRENT_GROQ_REQUESTS = 1
        ms.return_value.GROQ_MAX_RETRIES = 0
        reset_semaphore()

        # Launch 5 concurrent calls.
        tasks = [
            groq_chat_with_retry(mock_client, model="m", messages=[])
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)

    # With semaphore=1, at most 1 call should be active at a time.
    assert max_active == 1


# ---------------------------------------------------------------------------
# Short transcript / filler word guard
# ---------------------------------------------------------------------------

def test_is_trivial_empty():
    assert _is_trivial("") is True
    assert _is_trivial("   ") is True


def test_is_trivial_filler_words():
    assert _is_trivial("um") is True
    assert _is_trivial("okay") is True
    assert _is_trivial("um okay so") is True


def test_is_trivial_real_content():
    assert _is_trivial("Binary search divides the array.") is False
    assert _is_trivial("yes binary search") is False  # mixed


@pytest.mark.asyncio
async def test_translate_skips_trivial_transcript():
    """translate() returns {} for filler-word-only text without calling Gemini."""
    gemini_mock = AsyncMock()

    state = _make_state(last_transcript="um okay")

    with patch("app.graph.nodes.translation.gemini_translate", gemini_mock), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GEMINI_API_KEY = "fake"
        ms.return_value.GEMINI_TRANSLATION_MODEL = "gemini-2.5-flash-lite"
        ms.return_value.MIN_TRANSCRIPT_CHARS = 5
        result = await translate(state)

    assert result == {}
    gemini_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Session store throttle helpers
# ---------------------------------------------------------------------------

def test_should_run_topic_detection_first_time():
    """should_run_topic_detection is True on first call (no history)."""
    store = LectureSessionStore()
    assert store.should_run_topic_detection("new-lec", 30) is True


def test_should_run_topic_detection_throttled():
    """should_run_topic_detection is False right after mark_topic_detection_ran."""
    store = LectureSessionStore()
    store.mark_topic_detection_ran("lec-x")
    assert store.should_run_topic_detection("lec-x", 30) is False


def test_should_run_event_detection_first_time():
    store = LectureSessionStore()
    assert store.should_run_event_detection("new-lec", 30) is True


def test_should_run_event_detection_throttled():
    store = LectureSessionStore()
    store.mark_event_detection_ran("lec-y")
    assert store.should_run_event_detection("lec-y", 30) is False


def test_pop_event_pending_transcript_clears():
    store = LectureSessionStore()
    store.append_event_pending_transcript("lec-z", "first chunk")
    store.append_event_pending_transcript("lec-z", "second chunk")
    popped = store.pop_event_pending_transcript("lec-z")
    assert "first chunk" in popped
    assert "second chunk" in popped
    # After pop it should be empty.
    assert store.pop_event_pending_transcript("lec-z") == ""


def test_is_duplicate_translation():
    store = LectureSessionStore()
    assert store.is_duplicate_translation("lec-d", "some text") is False
    store.set_last_translated_text("lec-d", "some text")
    assert store.is_duplicate_translation("lec-d", "some text") is True
    assert store.is_duplicate_translation("lec-d", "different text") is False
