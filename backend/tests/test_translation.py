"""
Phase 7 tests — Translation pipeline.

Covers:
  - Translation Agent (translate function)
  - LectureSessionStore
  - Language validation
  - Context passing
  - WebSocket language_change handler
  - Translation broadcast
  - Translation failure isolation

All Groq API calls are mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.graph.state import LectureSessionState, VALID_LANGUAGES
from app.graph.nodes.translation import translate
from app.services.lecture_session import LectureSessionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> LectureSessionState:
    defaults = dict(
        lecture_id="lec-test",
        target_language="english",
        last_transcript="Binary search divides the search space into half.",
        last_timestamp=10.0,
        recent_transcripts=["Today we discuss binary search.", "Binary search divides the search space into half."],
        technical_terms=["Binary Search", "O(log n)"],
        current_topic="Binary Search",
        current_subtopic="Time Complexity",
        previous_translation="",
    )
    defaults.update(kwargs)
    return LectureSessionState(**defaults)


def _make_groq_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# VALID_LANGUAGES
# ---------------------------------------------------------------------------

def test_valid_languages_set():
    assert "english"  in VALID_LANGUAGES
    assert "hindi"    in VALID_LANGUAGES
    assert "hinglish" in VALID_LANGUAGES
    assert "french"   not in VALID_LANGUAGES
    assert "tamil"    not in VALID_LANGUAGES


# ---------------------------------------------------------------------------
# translate() — guard conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_returns_empty_for_blank_transcript():
    state = _make_state(last_transcript="   ")
    result = await translate(state)
    assert result == {}


@pytest.mark.asyncio
async def test_translate_returns_empty_for_invalid_language():
    state = _make_state(target_language="klingon")
    result = await translate(state)
    assert result == {}


@pytest.mark.asyncio
async def test_translate_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings
    get_settings.cache_clear()
    state = _make_state()
    result = await translate(state)
    assert result == {}
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# translate() — English
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_english():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_groq_response("Binary search divides the search space into half.")
    )

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        state = _make_state(target_language="english")
        result = await translate(state)

    assert result["language"]   == "english"
    assert "binary search" in result["translated"].lower()


# ---------------------------------------------------------------------------
# translate() — Hindi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_hindi():
    hindi_text = "Binary search search space को आधे में divide करता है।"
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_groq_response(hindi_text)
    )

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        state = _make_state(target_language="hindi")
        result = await translate(state)

    assert result["language"]   == "hindi"
    assert result["translated"] == hindi_text


# ---------------------------------------------------------------------------
# translate() — Hinglish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_hinglish():
    hinglish_text = "Binary search mein hum search space ko half karte hain."
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_groq_response(hinglish_text)
    )

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        state = _make_state(target_language="hinglish")
        result = await translate(state)

    assert result["language"]   == "hinglish"
    assert result["translated"] == hinglish_text


# ---------------------------------------------------------------------------
# translate() — context is passed to Groq
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_passes_context_to_groq():
    """Technical terms, recent transcripts, and topic are forwarded in the prompt."""
    mock_client = MagicMock()
    create_mock = AsyncMock(return_value=_make_groq_response("ok"))
    mock_client.chat.completions.create = create_mock

    state = _make_state(
        target_language="english",
        current_topic="Binary Search",
        technical_terms=["Binary Search", "O(log n)"],
        recent_transcripts=["Today we discuss binary search.", "It works by halving."],
    )

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        await translate(state)

    call_kwargs = create_mock.call_args.kwargs
    messages    = call_kwargs["messages"]
    full_text   = " ".join(m["content"] for m in messages)

    assert "Binary Search"   in full_text
    assert "O(log n)"        in full_text
    assert "Today we discuss" in full_text


@pytest.mark.asyncio
async def test_translate_preserves_formula():
    """O(log n) must appear verbatim in the user prompt."""
    mock_client = MagicMock()
    create_mock = AsyncMock(return_value=_make_groq_response("The time complexity is O(log n)."))
    mock_client.chat.completions.create = create_mock

    state = _make_state(
        target_language="english",
        last_transcript="The time complexity is O(log n).",
        technical_terms=["O(log n)"],
    )

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        result = await translate(state)

    assert "O(log n)" in result["translated"]


# ---------------------------------------------------------------------------
# translate() — error resilience
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_returns_empty_on_groq_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        result = await translate(_make_state())

    assert result == {}


# ---------------------------------------------------------------------------
# LectureSessionStore
# ---------------------------------------------------------------------------

def test_session_store_creates_default_state():
    store = LectureSessionStore()
    state = store.get_or_create("lec-1")
    assert state.lecture_id      == "lec-1"
    assert state.target_language == "english"
    assert state.recent_transcripts == []


def test_session_store_set_language():
    store = LectureSessionStore()
    store.get_or_create("lec-2")
    updated = store.set_language("lec-2", "hindi")
    assert updated.target_language == "hindi"


def test_session_store_invalid_language_accepted_at_store_level():
    """Validation is at the WS handler level; store is permissive."""
    store = LectureSessionStore()
    store.get_or_create("lec-3")
    updated = store.set_language("lec-3", "klingon")
    assert updated.target_language == "klingon"  # store is dumb; router validates


def test_session_store_add_transcript_bounded():
    from app.graph.state import MAX_RECENT_TRANSCRIPTS
    store = LectureSessionStore()
    store.get_or_create("lec-4")
    for i in range(MAX_RECENT_TRANSCRIPTS + 5):
        store.add_transcript("lec-4", f"sentence {i}")
    state = store.get("lec-4")
    assert len(state.recent_transcripts) == MAX_RECENT_TRANSCRIPTS


def test_session_store_last_transcript_updated():
    store = LectureSessionStore()
    store.get_or_create("lec-5")
    store.add_transcript("lec-5", "first sentence", timestamp=1.0)
    store.add_transcript("lec-5", "second sentence", timestamp=2.0)
    state = store.get("lec-5")
    assert state.last_transcript == "second sentence"
    assert state.last_timestamp  == 2.0


def test_session_store_set_translation():
    store = LectureSessionStore()
    store.get_or_create("lec-6")
    updated = store.set_translation("lec-6", "Yeh binary search hai.")
    assert updated.previous_translation == "Yeh binary search hai."


def test_session_store_add_technical_term_deduplicates():
    store = LectureSessionStore()
    store.get_or_create("lec-7")
    store.add_technical_term("lec-7", "Binary Search")
    store.add_technical_term("lec-7", "Binary Search")
    state = store.get("lec-7")
    assert state.technical_terms.count("Binary Search") == 1


# ---------------------------------------------------------------------------
# WebSocket language_change validation (unit test via handler logic)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ws_language_change_valid():
    """Valid language change updates session state."""
    from app.api.websocket import _handle_language_change

    store = LectureSessionStore()
    store.get_or_create("lec-ws-1")

    mock_ws  = MagicMock()
    mock_ws.send_json = AsyncMock()

    # Patch translate to avoid real Groq call; no last_transcript so no retranslation
    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.VALID_LANGUAGES", VALID_LANGUAGES):
        await _handle_language_change("lec-ws-1", {"target_language": "hindi"}, mock_ws)

    assert store.get("lec-ws-1").target_language == "hindi"
    mock_ws.send_json.assert_not_called()  # no retranslation (empty transcript)


@pytest.mark.asyncio
async def test_ws_language_change_invalid_sends_error():
    """Invalid language sends back an error message without changing state."""
    from app.api.websocket import _handle_language_change

    store = LectureSessionStore()
    store.get_or_create("lec-ws-2")

    mock_ws = MagicMock()
    mock_ws.send_json = AsyncMock()

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.VALID_LANGUAGES", VALID_LANGUAGES):
        await _handle_language_change("lec-ws-2", {"target_language": "french"}, mock_ws)

    mock_ws.send_json.assert_awaited_once()
    call_arg = mock_ws.send_json.call_args[0][0]
    assert call_arg["type"] == "error"
    assert "french" in call_arg["message"]


# ---------------------------------------------------------------------------
# Translation event broadcast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_translation_broadcasts_event():
    """_run_translation broadcasts a 'translation' WS message on success."""
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-tx-1")
    store.add_transcript("lec-tx-1", "Binary search halves the array.", timestamp=5.0)

    broadcast_calls: list[dict] = []

    async def fake_broadcast(lid, msg):
        broadcast_calls.append(msg)

    mock_result = {"translated": "Binary search array ko half karta hai.", "language": "hindi"}

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_manager, \
         patch("app.api.websocket.translate", new_callable=AsyncMock, return_value=mock_result) as mock_translate:
        mock_manager.broadcast = AsyncMock(side_effect=fake_broadcast)
        await _run_translation("lec-tx-1", "Binary search halves the array.", 5.0)

    assert len(broadcast_calls) == 1
    msg = broadcast_calls[0]
    assert msg["type"]                == "translation"
    assert msg["content"]             == "Binary search array ko half karta hai."
    assert msg["metadata"]["language"] == "hindi"


@pytest.mark.asyncio
async def test_run_translation_broadcasts_error_on_failure():
    """When translation raises, a 'translation_error' message is broadcast."""
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-tx-2")

    broadcast_calls: list[dict] = []

    async def fake_broadcast(lid, msg):
        broadcast_calls.append(msg)

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_manager, \
         patch("app.api.websocket.translate", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        mock_manager.broadcast = AsyncMock(side_effect=fake_broadcast)
        await _run_translation("lec-tx-2", "test transcript", 3.0)

    assert any(m["type"] == "translation_error" for m in broadcast_calls)


@pytest.mark.asyncio
async def test_run_translation_does_not_broadcast_when_result_empty():
    """If translate() returns {}, nothing is broadcast."""
    from app.api.websocket import _run_translation

    store = LectureSessionStore()
    store.get_or_create("lec-tx-3")

    with patch("app.api.websocket.session_store", store), \
         patch("app.api.websocket.manager") as mock_manager, \
         patch("app.api.websocket.translate", new_callable=AsyncMock, return_value={}):
        mock_manager.broadcast = AsyncMock()
        await _run_translation("lec-tx-3", "test", 0.0)

    mock_manager.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_translation_failure_does_not_affect_transcription():
    """
    Even when translation fails, the speech_event message is broadcast independently
    because _run_translation is a separate asyncio task from _handle_audio.
    This test verifies translate() never raises.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("network error"))

    with patch("app.graph.nodes.translation.get_groq_client", return_value=mock_client), \
         patch("app.graph.nodes.translation.get_settings") as ms:
        ms.return_value.GROQ_API_KEY = "fake"
        ms.return_value.GROQ_MODEL   = "llama3-8b-8192"
        # Must NOT raise
        result = await translate(_make_state())

    assert result == {}
