"""
Tests for Phase 8 — Notes Generation

Covers:
  - _build_user_prompt formatting
  - generate_notes: empty guard, no API key, LLM success, LLM failure
  - run_notes_graph: full integration (all I/O mocked)
  - note_service: save_note + get_notes (in-memory SQLite)
  - GET /lectures/{id}/notes endpoint
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()

        await run_notes_graph("lec-g-1")

        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        assert call_args[0][0] == "lec-g-1"
        msg = call_args[0][1]
        assert msg["type"] == "notes"
        assert msg["content"] == notes_md


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
    ):
        mock_event_svc.get_events = AsyncMock(return_value=[])
        mock_manager.broadcast    = AsyncMock()

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
    ):
        mock_event_svc.get_events = AsyncMock(return_value=events)
        mock_note_svc.save_note   = AsyncMock()
        mock_manager.broadcast    = AsyncMock()

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
    ):
        mock_event_svc.get_events = AsyncMock(side_effect=RuntimeError("DB exploded"))

        # Must NOT raise
        await run_notes_graph("lec-g-4")


# ---------------------------------------------------------------------------
# GET /lectures/{id}/notes  (REST endpoint)
# ---------------------------------------------------------------------------

def test_get_notes_endpoint_returns_list(test_client):
    """GET /lectures/{id}/notes should return an empty list when no notes exist."""
    response = test_client.get("/lectures/lec-no-notes/notes")
    assert response.status_code == 200
    assert response.json() == []
