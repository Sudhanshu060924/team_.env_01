"""
Phase 9 tests — Topic Detection & Important Event Detection

Covers:
  - detect_topic: guard conditions, Groq success, changed/unchanged, error handling
  - detect_important_events: guard conditions, Groq success, formula tagging, error handling
  - _run_topic_detection: broadcasts topic_update only when changed
  - _run_important_event_detection: broadcasts one important_event per item
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.state import LectureSessionState
from app.graph.nodes.supervisor import detect_topic
from app.graph.nodes.router import detect_important_events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> LectureSessionState:
    defaults = dict(
        lecture_id="lec-t",
        target_language="english",
        last_transcript="Binary search divides the array in half each step.",
        last_timestamp=5.0,
        recent_transcripts=[
            "Today we look at searching algorithms.",
            "Binary search divides the array in half each step.",
        ],
        current_topic="",
        current_subtopic="",
    )
    defaults.update(kwargs)
    return LectureSessionState(**defaults)


def _mock_groq_text(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# detect_topic — guard conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_topic_empty_transcript_returns_empty():
    state = _make_state(last_transcript="")
    result = await detect_topic(state)
    assert result == {}


@pytest.mark.asyncio
async def test_detect_topic_whitespace_transcript_returns_empty():
    state = _make_state(last_transcript="   ")
    result = await detect_topic(state)
    assert result == {}


@pytest.mark.asyncio
async def test_detect_topic_no_api_key_returns_empty():
    state = _make_state()
    with patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = ""
        result = await detect_topic(state)
    assert result == {}


# ---------------------------------------------------------------------------
# detect_topic — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_topic_returns_topic_and_subtopic():
    payload = json.dumps({"topic": "Binary Search", "subtopic": "Time Complexity"})
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(_make_state())

    assert result["topic"]    == "Binary Search"
    assert result["subtopic"] == "Time Complexity"


@pytest.mark.asyncio
async def test_detect_topic_changed_true_when_topic_differs():
    """changed=True when the detected topic is different from current."""
    payload = json.dumps({"topic": "Sorting", "subtopic": "Merge Sort"})
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    state = _make_state(current_topic="Binary Search", current_subtopic="Time Complexity")

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(state)

    assert result["changed"] is True


@pytest.mark.asyncio
async def test_detect_topic_changed_false_when_same():
    """changed=False when topic is identical to current state."""
    payload = json.dumps({"topic": "Binary Search", "subtopic": "Time Complexity"})
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    state = _make_state(current_topic="Binary Search", current_subtopic="Time Complexity")

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(state)

    assert result["changed"] is False


@pytest.mark.asyncio
async def test_detect_topic_empty_topic_not_changed():
    """changed=False when LLM returns empty topic (cannot detect)."""
    payload = json.dumps({"topic": "", "subtopic": ""})
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(_make_state())

    assert result["changed"] is False


@pytest.mark.asyncio
async def test_detect_topic_groq_error_returns_empty():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(_make_state())

    assert result == {}


@pytest.mark.asyncio
async def test_detect_topic_invalid_json_returns_empty():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_groq_text("not valid json at all")
    )

    with patch("app.graph.nodes.supervisor.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.supervisor.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_TOPIC_CONTEXT_CHARS = 5000
        result = await detect_topic(_make_state())

    assert result == {}


# ---------------------------------------------------------------------------
# detect_important_events — guard conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_important_events_empty_transcript_returns_list():
    result = await detect_important_events("", 0.0, "lec-ie-1")
    assert result == []


@pytest.mark.asyncio
async def test_detect_important_events_no_api_key_returns_list():
    with patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = ""
        result = await detect_important_events("Binary search is O(log n).", 1.0, "lec-ie-2")
    assert result == []


# ---------------------------------------------------------------------------
# detect_important_events — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_important_events_success():
    payload = json.dumps([
        {"content": "Binary search time complexity is O(log n).", "is_formula": True},
        {"content": "Binary search requires a sorted array.", "is_formula": False},
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events(
            "Binary search time complexity is O(log n). It requires a sorted array.",
            3.0, "lec-ie-3",
        )

    assert len(result) == 2
    assert result[0]["is_formula"] is True
    assert "O(log n)" in result[0]["content"]
    assert result[1]["is_formula"] is False


@pytest.mark.asyncio
async def test_detect_important_events_empty_array_result():
    """LLM returning [] means nothing important found."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text("[]"))

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events("Some ordinary speech.", 4.0, "lec-ie-4")

    assert result == []


@pytest.mark.asyncio
async def test_detect_important_events_skips_items_with_empty_content():
    payload = json.dumps([
        {"content": "", "is_formula": False},   # empty — should be skipped
        {"content": "The base case is n==0.", "is_formula": False},
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_groq_text(payload))

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events("Recursion base case.", 5.0, "lec-ie-5")

    assert len(result) == 1
    assert "base case" in result[0]["content"]


@pytest.mark.asyncio
async def test_detect_important_events_groq_error_returns_empty():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events("Some speech.", 6.0, "lec-ie-6")

    assert result == []


@pytest.mark.asyncio
async def test_detect_important_events_invalid_json_returns_empty():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_groq_text("here are the key facts: (1) ...")
    )

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events("Some speech.", 7.0, "lec-ie-7")

    assert result == []


@pytest.mark.asyncio
async def test_detect_important_events_non_list_json_returns_empty():
    """LLM returns a JSON object instead of array — should handle gracefully."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_groq_text('{"content": "something", "is_formula": false}')
    )

    with patch("app.graph.nodes.router.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.router.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "sk-test"
        ms.return_value.GROQ_MODEL   = "llama-3.1-8b-instant"
        ms.return_value.MAX_EVENT_CONTEXT_CHARS = 5000
        result = await detect_important_events("Some speech.", 8.0, "lec-ie-8")

    assert result == []


# ---------------------------------------------------------------------------
# _run_topic_detection — WS broadcast integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_topic_detection_broadcasts_when_changed():
    from app.api.websocket import _run_topic_detection
    from app.services.lecture_session import LectureSessionStore
    from unittest.mock import MagicMock

    store = LectureSessionStore()
    store.get_or_create("lec-td-1")

    broadcasts: list[dict] = []

    async def fake_broadcast(lid, msg):
        broadcasts.append(msg)

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", new_callable=AsyncMock,
               return_value={"topic": "Recursion", "subtopic": "Base Case", "changed": True}), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock(side_effect=fake_broadcast)
        await _run_topic_detection("lec-td-1", 10.0)

    assert len(broadcasts) == 1
    msg = broadcasts[0]
    assert msg["type"]    == "topic_update"
    assert msg["content"] == "Recursion"
    assert msg["metadata"]["subtopic"] == "Base Case"


@pytest.mark.asyncio
async def test_run_topic_detection_no_broadcast_when_unchanged():
    from app.api.websocket import _run_topic_detection
    from app.services.lecture_session import LectureSessionStore
    from unittest.mock import MagicMock

    store = LectureSessionStore()
    store.get_or_create("lec-td-2")

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", new_callable=AsyncMock,
               return_value={"topic": "Binary Search", "subtopic": "", "changed": False}), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_topic_detection("lec-td-2", 5.0)

    mock_mgr.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_run_topic_detection_no_broadcast_when_empty():
    from app.api.websocket import _run_topic_detection
    from app.services.lecture_session import LectureSessionStore
    from unittest.mock import MagicMock

    store = LectureSessionStore()
    store.get_or_create("lec-td-3")

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", new_callable=AsyncMock, return_value={}), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_topic_detection("lec-td-3", 5.0)

    mock_mgr.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_run_topic_detection_does_not_raise_on_error():
    from app.api.websocket import _run_topic_detection
    from app.services.lecture_session import LectureSessionStore
    from unittest.mock import MagicMock

    store = LectureSessionStore()
    store.get_or_create("lec-td-4")

    settings_mock = MagicMock()
    settings_mock.TOPIC_DETECTION_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_topic", new_callable=AsyncMock,
               side_effect=RuntimeError("boom")), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        # Must NOT raise
        await _run_topic_detection("lec-td-4", 5.0)


# ---------------------------------------------------------------------------
# _run_important_event_detection — WS broadcast integration
# (signature changed: transcript is now accumulated via session_store)
# ---------------------------------------------------------------------------

import time as _time


@pytest.mark.asyncio
async def test_run_important_event_detection_broadcasts_each_event():
    from app.api.websocket import _run_important_event_detection
    from app.services.lecture_session import LectureSessionStore

    events = [
        {"content": "O(log n) is the time complexity.", "is_formula": True},
        {"content": "The array must be sorted first.", "is_formula": False},
    ]

    broadcasts: list[dict] = []

    store = LectureSessionStore()
    store.get_or_create("lec-ie-w-1")
    # Allow throttle gate and pre-load accumulated transcript.
    store._last_event_detection["lec-ie-w-1"] = _time.monotonic() - 60
    store._event_pending_transcript["lec-ie-w-1"] = "O(log n) ..."

    async def fake_broadcast(lid, msg):
        broadcasts.append(msg)

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events",
               new_callable=AsyncMock, return_value=events), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock(side_effect=fake_broadcast)
        await _run_important_event_detection("lec-ie-w-1", 3.0)

    assert len(broadcasts) == 2
    assert broadcasts[0]["type"] == "important_event"
    assert broadcasts[0]["metadata"]["is_formula"] is True
    assert broadcasts[1]["metadata"]["is_formula"] is False


@pytest.mark.asyncio
async def test_run_important_event_detection_no_broadcasts_when_empty():
    from app.api.websocket import _run_important_event_detection
    from app.services.lecture_session import LectureSessionStore

    store = LectureSessionStore()
    store.get_or_create("lec-ie-w-2")
    store._last_event_detection["lec-ie-w-2"] = _time.monotonic() - 60
    store._event_pending_transcript["lec-ie-w-2"] = "ordinary text"

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        await _run_important_event_detection("lec-ie-w-2", 4.0)

    mock_mgr.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_run_important_event_detection_does_not_raise_on_error():
    from app.api.websocket import _run_important_event_detection
    from app.services.lecture_session import LectureSessionStore

    store = LectureSessionStore()
    store.get_or_create("lec-ie-w-3")
    store._last_event_detection["lec-ie-w-3"] = _time.monotonic() - 60
    store._event_pending_transcript["lec-ie-w-3"] = "text"

    settings_mock = MagicMock()
    settings_mock.IMPORTANT_EVENT_INTERVAL_SECONDS = 30

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_mgr, \
         patch("app.api.websocket.detect_important_events",
               new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("app.api.websocket.get_settings", return_value=settings_mock):
        mock_mgr.broadcast = AsyncMock()
        # Must NOT raise
        await _run_important_event_detection("lec-ie-w-3", 5.0)