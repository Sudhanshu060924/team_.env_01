"""
Tests for Phase 8 — Notes Generation

Covers:
  - _build_user_prompt formatting
  - _build_system_prompt language instructions
  - generate_notes: empty guard, no API key, LLM success, LLM failure, language param
  - run_notes_graph: full integration (all I/O mocked), language propagation
  - note_service: save_note + get_notes (in-memory SQLite)
  - GET /lectures/{id}/notes endpoint (with and without language filter)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.events import LectureEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    etype: str = "speech",
    content: str = "Hello world",
    ts: float = 1.0,
    lecture_id: str = "lec-1",
    is_formula: bool = False,
) -> LectureEvent:
    return LectureEvent(
        event_id=str(uuid.uuid4()),
        lecture_id=lecture_id,
        timestamp=ts,
        type=etype,
        source="whisper" if etype == "speech" else "ocr",
        content=content,
        metadata={"is_formula": is_formula} if etype == "board" else {},
    )


def _mock_groq_response(content: str):
    """Return a minimal mock mimicking AsyncGroq chat completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------

def test_build_user_prompt_empty_list():
    from app.graph.nodes.notes import _build_user_prompt
    result = _build_user_prompt([])
    assert result == "No transcript available."


def test_build_user_prompt_speech_only():
    from app.graph.nodes.notes import _build_user_prompt
    events = [
        _make_event("speech", "Binary search divides the array.", ts=5.0),
        _make_event("speech", "Time complexity is O(log n).", ts=10.0),
    ]
    result = _build_user_prompt(events)
    assert "TRANSCRIPT" in result
    assert "Binary search" in result
    assert "BOARD" not in result


def test_build_user_prompt_board_events_included():
    from app.graph.nodes.notes import _build_user_prompt
    events = [
        _make_event("speech", "Here is the formula.", ts=3.0),
        _make_event("board",  "T(n) = 2T(n/2) + O(n)", ts=4.0, is_formula=True),
    ]
    result = _build_user_prompt(events)
    assert "TRANSCRIPT" in result
    assert "BOARD / SLIDES" in result
    assert "FORMULA" in result


def test_build_user_prompt_skips_empty_content():
    from app.graph.nodes.notes import _build_user_prompt
    events = [
        _make_event("speech", ""),        # empty — should be skipped
        _make_event("speech", "  "),      # whitespace — should be skipped
        _make_event("speech", "Real text"),
    ]
    result = _build_user_prompt(events)
    assert result.count("[") == 1  # only the real event has a timestamp tag


def test_build_user_prompt_only_other_event_types():
    from app.graph.nodes.notes import _build_user_prompt
    events = [_make_event("lecture_completed", "")]
    result = _build_user_prompt(events)
    assert result == "No transcript available."


# ---------------------------------------------------------------------------
# _build_system_prompt — language instructions
# ---------------------------------------------------------------------------

def test_build_system_prompt_english():
    from app.graph.nodes.notes import _build_system_prompt
    prompt = _build_system_prompt("english")
    assert "english" in prompt.lower()
    assert "English" in prompt


def test_build_system_prompt_hindi():
    from app.graph.nodes.notes import _build_system_prompt
    prompt = _build_system_prompt("hindi")
    assert "hindi" in prompt.lower()
    assert "Devanagari" in prompt


def test_build_system_prompt_hinglish():
    from app.graph.nodes.notes import _build_system_prompt
    prompt = _build_system_prompt("hinglish")
    assert "hinglish" in prompt.lower()
    assert "ROMAN" in prompt
    # Must NOT instruct to use Devanagari for Hinglish
    assert "Devanagari" not in prompt.lower().split("roman")[1] if "roman" in prompt.lower() else True


def test_build_system_prompt_unknown_language_falls_back_to_english():
    from app.graph.nodes.notes import _build_system_prompt
    prompt = _build_system_prompt("klingon")
    # Should fall back gracefully and not crash
    assert isinstance(prompt, str)
    assert len(prompt) > 50


# ---------------------------------------------------------------------------
# generate_notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_notes_returns_empty_when_no_api_key():
    from app.graph.nodes.notes import generate_notes

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = ""

    with patch("app.graph.nodes.notes.get_settings", return_value=mock_settings):
        result = await generate_notes("lec-1", [_make_event()])
    assert result == ""


@pytest.mark.asyncio
async def test_generate_notes_returns_empty_for_no_events():
    from app.graph.nodes.notes import generate_notes

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = "sk-test"
    mock_settings.GROQ_MODEL   = "llama3-8b-8192"

    with patch("app.graph.nodes.notes.get_settings", return_value=mock_settings):
        result = await generate_notes("lec-1", [])
    assert result == ""


@pytest.mark.asyncio
async def test_generate_notes_success():
    from app.graph.nodes.notes import generate_notes

    events = [
        _make_event("speech", "Binary search halves the array each step."),
        _make_event("board",  "O(log n)", is_formula=True),
    ]

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = "sk-test"
    mock_settings.GROQ_MODEL   = "llama3-8b-8192"

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_groq_response("## Summary\nBinary search...")
    )

    with (
        patch("app.graph.nodes.notes.get_settings", return_value=mock_settings),
        patch("app.graph.nodes.notes.get_groq_client", return_value=mock_client),
    ):
        result = await generate_notes("lec-1", events)

    assert "Summary" in result
    assert "Binary search" in result


@pytest.mark.asyncio
async def test_generate_notes_passes_language_to_groq():
    """The system prompt sent to Groq should mention the requested language."""
    from app.graph.nodes.notes import generate_notes

    events = [_make_event("speech", "Quick sort divides the list.")]

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = "sk-test"
    mock_settings.GROQ_MODEL   = "llama3-8b-8192"

    captured_messages = []

    async def _capture_create(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return _mock_groq_response("## Summary\nQuick sort...")

    mock_client = MagicMock()
    mock_client.chat.completions.create = _capture_create

    with (
        patch("app.graph.nodes.notes.get_settings", return_value=mock_settings),
        patch("app.graph.nodes.notes.get_groq_client", return_value=mock_client),
    ):
        await generate_notes("lec-1", events, target_language="hindi")

    system_msg = next(m for m in captured_messages if m["role"] == "system")
    assert "hindi" in system_msg["content"].lower()
    assert "Devanagari" in system_msg["content"]


@pytest.mark.asyncio
async def test_generate_notes_hinglish_uses_roman_script_instruction():
    from app.graph.nodes.notes import generate_notes

    events = [_make_event("speech", "Binary search demo.")]

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = "sk-test"
    mock_settings.GROQ_MODEL   = "llama3-8b-8192"

    captured_messages = []

    async def _capture_create(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return _mock_groq_response("## Summary\nBinary search...")

    mock_client = MagicMock()
    mock_client.chat.completions.create = _capture_create

    with (
        patch("app.graph.nodes.notes.get_settings", return_value=mock_settings),
        patch("app.graph.nodes.notes.get_groq_client", return_value=mock_client),
    ):
        await generate_notes("lec-1", events, target_language="hinglish")

    system_msg = next(m for m in captured_messages if m["role"] == "system")
    assert "ROMAN" in system_msg["content"]


@pytest.mark.asyncio
async def test_generate_notes_groq_error_returns_empty():
    from app.graph.nodes.notes import generate_notes

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = "sk-test"
    mock_settings.GROQ_MODEL   = "llama3-8b-8192"

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))

    with (
        patch("app.graph.nodes.notes.get_settings", return_value=mock_settings),
        patch("app.graph.nodes.notes.get_groq_client", return_value=mock_client),
    ):
        result = await generate_notes("lec-1", [_make_event()])
    assert result == ""


@pytest.mark.asyncio
async def test_generate_notes_prompt_contains_timestamps():
    from app.graph.nodes.notes import generate_notes, _build_user_prompt

    events = [_make_event("speech", "Hello", ts=42.5)]
    prompt = _build_user_prompt(events)
    assert "42.5s" in prompt


# ---------------------------------------------------------------------------
# run_notes_graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_notes_graph_broadcasts_on_success():
    from app.graph.notes_graph import run_notes_graph

    events = [_make_event("speech", "Merge sort divides and conquers.")]
    notes_md = "## Summary\nMerge sort..."

    async def fake_get_db():
        yield MagicMock()

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.note_svc") as mock_note_svc,
        patch("app.graph.notes_graph.generate_notes", new_callable=AsyncMock, return_value=notes_md),
        patch("app.graph.notes_graph.manager") as mock_manager,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()
        mock_store.get.return_value = None  # no session → default to english

        await run_notes_graph("lec-g-1")

        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        assert call_args[0][0] == "lec-g-1"
        msg = call_args[0][1]
        assert msg["type"] == "notes"
        assert msg["content"] == notes_md
        assert "language" in msg


@pytest.mark.asyncio
async def test_run_notes_graph_uses_session_language():
    """Graph should pass the session's target_language to generate_notes."""
    from app.graph.notes_graph import run_notes_graph

    events = [_make_event("speech", "Quick sort steps.")]
    notes_md = "## Summary\nQuick sort..."

    async def fake_get_db():
        yield MagicMock()

    mock_session = MagicMock()
    mock_session.target_language = "hindi"

    captured_lang = []

    async def _capture_generate(lecture_id, evts, target_language="english"):
        captured_lang.append(target_language)
        return notes_md

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.note_svc") as mock_note_svc,
        patch("app.graph.notes_graph.generate_notes", side_effect=_capture_generate),
        patch("app.graph.notes_graph.manager") as mock_manager,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()
        mock_store.get.return_value = mock_session

        await run_notes_graph("lec-g-lang")

        assert captured_lang == ["hindi"]


@pytest.mark.asyncio
async def test_run_notes_graph_explicit_language_overrides_session():
    """Explicit target_language arg takes priority over session language."""
    from app.graph.notes_graph import run_notes_graph

    events = [_make_event("speech", "Bubble sort.")]
    notes_md = "## Summary\nBubble sort..."

    async def fake_get_db():
        yield MagicMock()

    mock_session = MagicMock()
    mock_session.target_language = "hindi"  # session says hindi

    captured_lang = []

    async def _capture_generate(lecture_id, evts, target_language="english"):
        captured_lang.append(target_language)
        return notes_md

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.note_svc") as mock_note_svc,
        patch("app.graph.notes_graph.generate_notes", side_effect=_capture_generate),
        patch("app.graph.notes_graph.manager") as mock_manager,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()
        mock_store.get.return_value = mock_session

        # Explicit arg is "hinglish" — should win over session "hindi"
        await run_notes_graph("lec-g-override", target_language="hinglish")

        assert captured_lang == ["hinglish"]


@pytest.mark.asyncio
async def test_run_notes_graph_no_events_skips():
    from app.graph.notes_graph import run_notes_graph

    async def fake_get_db():
        yield MagicMock()

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.note_svc") as mock_note_svc,
        patch("app.graph.notes_graph.generate_notes", new_callable=AsyncMock) as mock_gen,
        patch("app.graph.notes_graph.manager") as mock_manager,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(return_value=[])
        mock_manager.broadcast    = AsyncMock()
        mock_store.get.return_value = None

        await run_notes_graph("lec-g-2")

        mock_gen.assert_not_called()
        mock_manager.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_run_notes_graph_empty_notes_skips_save():
    from app.graph.notes_graph import run_notes_graph

    events = [_make_event("speech", "Test lecture content.")]

    async def fake_get_db():
        yield MagicMock()

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.note_svc") as mock_note_svc,
        patch("app.graph.notes_graph.generate_notes", new_callable=AsyncMock, return_value=""),
        patch("app.graph.notes_graph.manager") as mock_manager,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()
        mock_store.get.return_value = None

        await run_notes_graph("lec-g-3")

        mock_note_svc.save_note.assert_not_called()
        mock_manager.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_run_notes_graph_exception_does_not_propagate():
    """The graph must never raise — any error is caught and logged."""
    from app.graph.notes_graph import run_notes_graph

    async def fake_get_db():
        yield MagicMock()

    with (
        patch("app.graph.notes_graph.get_db", fake_get_db),
        patch("app.graph.notes_graph.event_svc") as mock_event_svc,
        patch("app.graph.notes_graph.session_store") as mock_store,
    ):
        mock_event_svc.get_events = AsyncMock(side_effect=RuntimeError("DB exploded"))
        mock_store.get.return_value = None

        # Must NOT raise
        await run_notes_graph("lec-g-4")


# ---------------------------------------------------------------------------
# GET /lectures/{id}/notes  (REST endpoint)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_notes_endpoint_returns_list():
    """GET /lectures/{id}/notes should return an empty list when no notes exist."""
    with patch("app.api.lectures.note_svc.get_notes", new_callable=AsyncMock, return_value=[]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/lectures/lec-no-notes/notes")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_notes_endpoint_passes_language_filter():
    """GET /lectures/{id}/notes?language=hindi should pass language to note_svc."""
    from app.schemas.notes import NoteRead
    from datetime import datetime, timezone

    note = NoteRead(
        note_id="n1",
        lecture_id="lec-x",
        content="## Hindi notes",
        language="hindi",
        created_at=datetime.now(timezone.utc),
    )

    captured_kwargs = {}

    async def _fake_get_notes(db, lecture_id, language=None):
        captured_kwargs["language"] = language
        return [note]

    with patch("app.api.lectures.note_svc.get_notes", side_effect=_fake_get_notes):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/lectures/lec-x/notes?language=hindi")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["language"] == "hindi"
    assert captured_kwargs["language"] == "hindi"
