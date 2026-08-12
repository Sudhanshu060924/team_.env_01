"""
Phase 5 tests — Speech service (Groq Whisper + AudioPreprocessor).

All tests patch both the Groq client and AudioPreprocessor so no real
network calls or FFmpeg processes are made.
"""
import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.speech_service import (
    transcribe_audio,
    _choose_model,
    _format_from_filename,
    WHISPER_TURBO,
    WHISPER_LARGE,
)
from app.services.audio_preprocessor import (
    AudioPreprocessor,
    AudioPreprocessingError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_wav_bytes(sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Return a minimal valid WAV (0.1 s silence) for use as mock preprocessor output."""
    buf = io.BytesIO()
    n_samples = int(sample_rate * 0.1)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples * channels)
    return buf.getvalue()


def _make_mock_preprocessor(wav_bytes: bytes | None = None) -> MagicMock:
    """Return a mock AudioPreprocessor whose clean_audio returns wav_bytes."""
    mock_proc = MagicMock(spec=AudioPreprocessor)
    mock_proc.clean_audio = AsyncMock(return_value=wav_bytes or _make_wav_bytes())
    return mock_proc


def _make_mock_groq_client(text: str = "Hello world", language: str = "en",
                            duration: float = 2.5) -> MagicMock:
    """Return a mock Groq client whose transcriptions.create returns a result."""
    transcription = MagicMock()
    transcription.text = f"  {text}  "
    transcription.language = language
    transcription.duration = duration

    client = MagicMock()
    client.audio.transcriptions.create = AsyncMock(return_value=transcription)
    return client


# ---------------------------------------------------------------------------
# _choose_model
# ---------------------------------------------------------------------------

def test_choose_model_default(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "turbo")
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
# _format_from_filename
# ---------------------------------------------------------------------------

def test_format_from_filename_webm():
    assert _format_from_filename("audio.webm") == "webm"

def test_format_from_filename_ogg():
    assert _format_from_filename("chunk.ogg") == "ogg"

def test_format_from_filename_mp4():
    assert _format_from_filename("clip.mp4") == "mp4"

def test_format_from_filename_m4a():
    assert _format_from_filename("clip.m4a") == "mp4"

def test_format_from_filename_unknown_defaults_to_webm():
    assert _format_from_filename("audio.xyz") == "webm"

def test_format_from_filename_no_extension():
    assert _format_from_filename("audiofile") == "webm"


# ---------------------------------------------------------------------------
# transcribe_audio — guard conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_returns_empty_for_empty_bytes():
    result = await transcribe_audio(b"")
    assert result["text"] == ""
    assert result["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings
    get_settings.cache_clear()
    result = await transcribe_audio(b"some audio")
    assert result["text"] == ""


# ---------------------------------------------------------------------------
# transcribe_audio — happy path: preprocessor + Groq called correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_calls_preprocessor():
    """SpeechService passes audio_bytes through AudioPreprocessor first."""
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client()

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        await transcribe_audio(b"raw audio", filename="chunk.webm",
                               _preprocessor=mock_proc)

    mock_proc.clean_audio.assert_awaited_once()
    call_args = mock_proc.clean_audio.call_args
    assert call_args.kwargs["input_format"] == "webm"


@pytest.mark.asyncio
async def test_transcribe_whisper_receives_cleaned_wav():
    """Groq API receives the WAV output from AudioPreprocessor, not the raw bytes."""
    cleaned_wav = _make_wav_bytes()
    mock_proc = _make_mock_preprocessor(cleaned_wav)
    mock_client = _make_mock_groq_client()

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        await transcribe_audio(b"raw audio", _preprocessor=mock_proc)

    create_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    # The file tuple sent to Groq must contain the cleaned WAV, not the original bytes
    _, file_obj = create_kwargs["file"]
    assert file_obj.read() == cleaned_wav


@pytest.mark.asyncio
async def test_transcribe_success_returns_text_and_language():
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client(text="Binary search divides the array", language="en")

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        result = await transcribe_audio(b"audio bytes", _preprocessor=mock_proc)

    assert result["text"] == "Binary search divides the array"
    assert result["language"] == "en"
    assert result["duration"] == 2.5


@pytest.mark.asyncio
async def test_transcribe_uses_turbo_model_by_default():
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client()
    create_mock = mock_client.audio.transcriptions.create

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        await transcribe_audio(b"audio bytes", _preprocessor=mock_proc)

    assert create_mock.call_args.kwargs["model"] == WHISPER_TURBO


@pytest.mark.asyncio
async def test_transcribe_passes_language_hint():
    """Explicit language hint is forwarded to the Groq API."""
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client()
    create_mock = mock_client.audio.transcriptions.create

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        await transcribe_audio(b"audio", language="hi", _preprocessor=mock_proc)

    assert create_mock.call_args.kwargs["language"] == "hi"


@pytest.mark.asyncio
async def test_transcribe_uses_whisper_language_env_var(monkeypatch):
    """WHISPER_LANGUAGE env var is used when no explicit language is given."""
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client()
    create_mock = mock_client.audio.transcriptions.create

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = "en"

        await transcribe_audio(b"audio", _preprocessor=mock_proc)

    assert create_mock.call_args.kwargs.get("language") == "en"


# ---------------------------------------------------------------------------
# transcribe_audio — error resilience
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_returns_empty_when_preprocessing_fails():
    """AudioPreprocessingError is caught; empty result returned — WS handler safe."""
    mock_proc = MagicMock(spec=AudioPreprocessor)
    mock_proc.clean_audio = AsyncMock(
        side_effect=AudioPreprocessingError("FFmpeg failed")
    )

    with patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        result = await transcribe_audio(b"audio bytes", _preprocessor=mock_proc)

    assert result["text"] == ""
    assert result["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_returns_empty_on_groq_error():
    """Groq API exception is caught; empty result returned."""
    mock_proc = _make_mock_preprocessor()
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        side_effect=RuntimeError("API down")
    )

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        result = await transcribe_audio(b"audio bytes", _preprocessor=mock_proc)

    assert result["text"] == ""


@pytest.mark.asyncio
async def test_transcribe_lecture_event_contract():
    """
    Verify the dict returned matches the LectureEvent 'content' / 'language'
    fields expected by the WebSocket handler.
    """
    mock_proc = _make_mock_preprocessor()
    mock_client = _make_mock_groq_client(
        text="The time complexity is O(log n)", language="en"
    )

    with patch("app.services.speech_service.get_groq_client", return_value=mock_client), \
         patch("app.services.speech_service.get_settings") as mock_settings:
        mock_settings.return_value.GROQ_API_KEY = "fake-key"
        mock_settings.return_value.WHISPER_MODEL = "turbo"
        mock_settings.return_value.WHISPER_LANGUAGE = ""

        result = await transcribe_audio(b"audio bytes", _preprocessor=mock_proc)

    # These are the exact keys the WebSocket handler reads
    assert "text" in result
    assert "language" in result
    assert result["text"] == "The time complexity is O(log n)"
