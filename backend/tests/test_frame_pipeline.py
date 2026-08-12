"""
Phase 6 tests — Frame pipeline (frontend → WebSocket → VisionService).

Covers:
  1. Frame sent through WebSocket is dispatched to _handle_frame.
  2. Timestamp is included in the payload.
  3. A significant frame triggers a board_event broadcast.
  4. A non-significant frame does NOT trigger a broadcast.
  5. Empty / corrupt base64 data is handled gracefully.
  6. Audio pipeline is not broken by the new frame code.
  7. Translation pipeline still works alongside frame capture.
"""
from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64_jpeg(value: int = 128, size: int = 256) -> str:
    """Return a base64-encoded fake image blob (not a real JPEG — we mock cv2)."""
    return base64.b64encode(bytes([value]) * size).decode()


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# 1 + 2. Frame message dispatched via WebSocket; timestamp present
# ---------------------------------------------------------------------------

def test_frame_message_reaches_handle_frame(client):
    """
    Sending {"type": "frame", ...} over WebSocket must dispatch _handle_frame.
    Timestamp must be preserved in the call arguments.
    """
    import app.api.websocket as ws_mod

    handle_frame_calls: list[dict] = []

    async def fake_handle_frame(lecture_id: str, data: dict):
        handle_frame_calls.append({"lecture_id": lecture_id, **data})

    with patch.object(ws_mod, "_handle_frame", side_effect=fake_handle_frame):
        with client.websocket_connect("/ws/lectures/lec-vision-1") as ws:
            ws.receive_json()  # greeting
            ws.send_json({
                "type":       "frame",
                "lecture_id": "lec-vision-1",
                "timestamp":  14.0,
                "data":       _b64_jpeg(),
            })
            import time; time.sleep(0.15)

    assert len(handle_frame_calls) >= 1, "frame message was not dispatched to _handle_frame"
    assert handle_frame_calls[0]["timestamp"] == 14.0, "timestamp not preserved"


# ---------------------------------------------------------------------------
# 3. Significant frame → board_event broadcast (async unit test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_significant_frame_broadcasts_board_event():
    """
    _handle_frame with a mocked VisionService returning significant=True
    must call manager.broadcast with a board_event payload containing the
    OCR text and correct timestamp.
    """
    import app.api.websocket as ws_mod
    import app.services.vision_service as vsmod

    mock_process = MagicMock(return_value={
        "significant": True,
        "ocr_text":    "Newton's Second Law: F = ma",
        "is_formula":  True,
    })

    broadcast_calls: list[dict] = []

    async def fake_broadcast(lecture_id: str, payload: dict):
        broadcast_calls.append(payload)

    async def _noop_db():
        yield None

    with (
        patch.object(vsmod, "process_frame", mock_process),
        patch.object(ws_mod.manager, "broadcast", side_effect=fake_broadcast),
        patch("app.database.database.get_db", side_effect=_noop_db),
        patch("app.services.event_service.save_event", new_callable=AsyncMock),
    ):
        await ws_mod._handle_frame("lec-vision-2", {
            "timestamp": 30.0,
            "data":      _b64_jpeg(200),
        })

    board_events = [m for m in broadcast_calls if m.get("type") == "board_event"]
    assert len(board_events) >= 1, "board_event was not broadcast for significant frame"
    evt = board_events[0]
    assert evt["timestamp"] == 30.0
    assert "Newton" in evt["content"]
    assert evt["metadata"]["is_formula"] is True


# ---------------------------------------------------------------------------
# 4. Non-significant frame → no broadcast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_significant_frame_no_broadcast():
    """
    When process_frame returns significant=False, manager.broadcast must
    not be called with a board_event.
    """
    import app.api.websocket as ws_mod
    import app.services.vision_service as vsmod

    mock_process = MagicMock(return_value={
        "significant": False,
        "ocr_text":    "",
        "is_formula":  False,
    })

    broadcast_calls: list[dict] = []

    async def fake_broadcast(lecture_id: str, payload: dict):
        broadcast_calls.append(payload)

    with (
        patch.object(vsmod, "process_frame", mock_process),
        patch.object(ws_mod.manager, "broadcast", side_effect=fake_broadcast),
    ):
        await ws_mod._handle_frame("lec-vision-3", {
            "timestamp": 5.0,
            "data":      _b64_jpeg(100),
        })

    board_events = [m for m in broadcast_calls if m.get("type") == "board_event"]
    assert board_events == [], "board_event should NOT be broadcast for non-significant frame"


# ---------------------------------------------------------------------------
# 5. Corrupt / empty base64 handled gracefully (no unhandled exception)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_corrupt_frame_data_does_not_crash():
    """
    Corrupt base64 string must be caught inside _handle_frame; no exception
    should propagate to the caller.
    """
    import app.api.websocket as ws_mod

    # Must not raise
    await ws_mod._handle_frame("lec-vision-4", {
        "timestamp": 1.0,
        "data":      "!!!not-valid-base64!!!",
    })


@pytest.mark.asyncio
async def test_empty_frame_data_does_not_crash():
    """Empty data string must be handled gracefully."""
    import app.api.websocket as ws_mod

    await ws_mod._handle_frame("lec-vision-5", {
        "timestamp": 0.0,
        "data":      "",
    })


# ---------------------------------------------------------------------------
# 6. Audio pipeline not broken by new frame code
# ---------------------------------------------------------------------------

def test_audio_pipeline_unaffected_by_frame_code(client):
    """
    Sending an audio_chunk message must still invoke _handle_audio exactly
    as before; the presence of frame handling must not interfere.
    """
    import app.api.websocket as ws_mod

    handle_audio_calls: list[dict] = []

    async def fake_handle_audio(lecture_id: str, data: dict):
        handle_audio_calls.append({"lecture_id": lecture_id, **data})

    with patch.object(ws_mod, "_handle_audio", side_effect=fake_handle_audio):
        with client.websocket_connect("/ws/lectures/lec-audio-compat") as ws:
            ws.receive_json()  # greeting
            ws.send_json({
                "type":       "audio_chunk",
                "lecture_id": "lec-audio-compat",
                "timestamp":  10.0,
                "filename":   "audio.webm",
                "data":       base64.b64encode(b"\x00" * 600).decode(),
            })
            import time; time.sleep(0.15)

    assert len(handle_audio_calls) >= 1, "audio_chunk was not dispatched to _handle_audio"
    assert handle_audio_calls[0]["timestamp"] == 10.0


# ---------------------------------------------------------------------------
# 7. Translation pipeline still works alongside frame capture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translation_pipeline_still_works():
    """
    _handle_audio must still broadcast speech_event and translation.
    Tested at unit level (direct async call) to avoid WebSocket timing issues.
    """
    import app.api.websocket as ws_mod

    broadcast_calls: list[dict] = []

    async def fake_broadcast(lecture_id: str, payload: dict):
        broadcast_calls.append(payload)

    mock_session_state = MagicMock()
    mock_session_state.last_transcript = "hello world"
    mock_session_state.last_timestamp  = 5.0
    mock_session_state.target_language = "english"

    async def _noop_db():
        yield None

    with (
        patch("app.services.speech_service.transcribe_audio",
              new=AsyncMock(return_value={"text": "hello world", "language": "en"})),
        # Patch the name as imported in websocket.py (not the original module)
        patch("app.api.websocket.translate",
              new=AsyncMock(return_value={"translated": "Hola mundo", "language": "spanish"})),
        patch("app.api.websocket.detect_topic",
              new=AsyncMock(return_value={"changed": False})),
        patch("app.api.websocket.detect_important_events",
              new=AsyncMock(return_value=[])),
        patch("app.services.event_service.save_event", new_callable=AsyncMock),
        patch("app.database.database.get_db", side_effect=_noop_db),
        patch("app.services.lecture_session.session_store.add_transcript",
              return_value=mock_session_state),
        patch("app.services.lecture_session.session_store.set_translation"),
        patch.object(ws_mod.manager, "broadcast", side_effect=fake_broadcast),
    ):
        await ws_mod._handle_audio("lec-translation-compat", {
            "timestamp": 5.0,
            "filename":  "audio.webm",
            "data":      base64.b64encode(b"\x00" * 600).decode(),
        })
        # Allow the background tasks (_run_translation etc.) to settle
        await asyncio.sleep(0.15)

    types_received = {m["type"] for m in broadcast_calls}
    assert "speech_event" in types_received, "speech_event not broadcast"
    assert "translation"  in types_received, "translation not broadcast"

    translation_msg = next(m for m in broadcast_calls if m["type"] == "translation")
    assert translation_msg["content"] == "Hola mundo"
