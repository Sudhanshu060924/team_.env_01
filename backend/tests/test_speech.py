"""
Phase 5 tests — Speech service (Groq Whisper).

All tests patch the Groq client so no real network calls are made.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.speech_service import transcribe_audio, _choose_model, WHISPER_TURBO, WHISPER_LARGE


# ---------------------------------------------------------------------------
# _choose_model
# ---------------------------------------------------------------------------

def test_choose_model_default(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "turbo")
    # Clear lru_cache so new env value is picked up
    from app.config import get_settings
    get_settings.cache_clear()
    assert _choose_model() == WHISPER_TURBO


def test_choose_model_large(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "large")
    from app.config import get_settings
    get_settings.cache_clear()
    assert _choose_model() == WHISPER_LARGE


def test_choose_model_full_name_large(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "whisper-large-v3")
    from app.config import get_settings
    get_settings.cache_clear()
    assert _choose_model() == WHISPER_LARGE


def test_choose_model_unknown_falls_back_to_turbo(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "small")
    from app.config import get_settings
    get_settings.cache_clear()
    assert _choose_model() == WHISPER_TURBO


# ---------------------------------------------------------------------------
# transcribe_audio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings
    get_settings.cache_clear()

    result = await transcribe_audio(b"some audio bytes")
    assert result["text"] == ""
    assert result["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_returns_empty_for_empty_bytes(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from app.config import get_settings
    get_settings.cache_clear()

    result = await transcribe_audio(b"")
    assert result["text"] == ""


@pytest.mark.asyncio
async def test_transcribe_success():
    """Successful transcription returns text and language."""
    mock_transcription = MagicMock()
    mock_transcription.text = "  Hello world  "
    mock_transcription.language = "en"
    mock_transcription.duration = 2.5

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcription)

    with (
        patch("app.services.speech_service.get_groq_client", return_value=mock_client),
        patch("app.services.speech_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"

        result = await transcribe_audio(b"audio bytes", filename="chunk.webm")

    assert result["text"] == "Hello world"
    assert result["language"] == "en"
    assert result["duration"] == 2.5


@pytest.mark.asyncio
async def test_transcribe_passes_language_hint():
    """When a language hint is supplied it is forwarded to the API."""
    mock_transcription = MagicMock()
    mock_transcription.text = "Bonjour"
    mock_transcription.language = "fr"

    mock_client = MagicMock()
    create_mock = AsyncMock(return_value=mock_transcription)
    mock_client.audio.transcriptions.create = create_mock

    with (
        patch("app.services.speech_service.get_groq_client", return_value=mock_client),
        patch("app.services.speech_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"

        await transcribe_audio(b"audio", language="fr")

    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["language"] == "fr"


@pytest.mark.asyncio
async def test_transcribe_returns_empty_on_api_error():
    """Any API exception is caught and an empty result is returned."""
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=RuntimeError("API down"))

    with (
        patch("app.services.speech_service.get_groq_client", return_value=mock_client),
        patch("app.services.speech_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"

        result = await transcribe_audio(b"audio bytes")

    assert result["text"] == ""
    assert result["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_uses_turbo_model_by_default():
    """Verify the model forwarded to the API is whisper-large-v3-turbo."""
    mock_transcription = MagicMock()
    mock_transcription.text = "test"
    mock_transcription.language = "en"

    mock_client = MagicMock()
    create_mock = AsyncMock(return_value=mock_transcription)
    mock_client.audio.transcriptions.create = create_mock

    with (
        patch("app.services.speech_service.get_groq_client", return_value=mock_client),
        patch("app.services.speech_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"

        await transcribe_audio(b"audio bytes")

    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["model"] == WHISPER_TURBO
