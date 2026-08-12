"""
Speech service — Phase 5

Transcribes audio using the Groq Whisper API (whisper-large-v3-turbo by default).

The public interface is a single async function::

    result = await transcribe_audio(audio_bytes, filename="chunk.webm")

Returns::

    {
        "text":     "Hello, this is the transcribed speech.",
        "language": "en",          # detected language code
        "duration": 4.32,          # seconds (only present for verbose_json)
    }

If the API key is missing or empty the service returns an empty result instead
of raising, so that the WebSocket handler can continue without crashing.
"""
import io
import logging

from app.config import get_settings
from app.integrations.groq_service import get_groq_client

logger = logging.getLogger(__name__)

# Groq's available Whisper models
WHISPER_TURBO = "whisper-large-v3-turbo"
WHISPER_LARGE = "whisper-large-v3"

_EMPTY: dict = {"text": "", "language": "en"}


def _choose_model() -> str:
    """
    Pick the model from settings.WHISPER_MODEL.
    Accepts the short alias 'turbo' / 'large' or the full model name.
    Falls back to whisper-large-v3-turbo.
    """
    alias = get_settings().WHISPER_MODEL.lower().strip()
    if alias in ("large", WHISPER_LARGE):
        return WHISPER_LARGE
    return WHISPER_TURBO   # default: 'turbo', 'small', or any unrecognised value


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language: str | None = None,
    prompt: str | None = None,
) -> dict:
    """
    Transcribe *audio_bytes* via the Groq Whisper API.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio data (WebM, MP3, MP4, OGG, WAV, FLAC, …).
    filename : str
        Passed to the multipart upload so the API can sniff the format.
    language : str | None
        ISO-639-1 hint (e.g. ``"en"``, ``"hi"``).  Leave None to auto-detect.
    prompt : str | None
        Optional preceding context to improve accuracy.

    Returns
    -------
    dict  with keys ``text`` (str), ``language`` (str), and optionally ``duration`` (float).
    """
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        logger.warning("speech_service: GROQ_API_KEY is not set — returning empty transcript")
        return _EMPTY

    if not audio_bytes:
        return _EMPTY

    model = _choose_model()
    client = get_groq_client()

    try:
        file_tuple = (filename, io.BytesIO(audio_bytes))

        kwargs: dict = dict(
            file=file_tuple,
            model=model,
            response_format="verbose_json",
        )
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        transcription = await client.audio.transcriptions.create(**kwargs)

        result: dict = {
            "text": (transcription.text or "").strip(),
            "language": getattr(transcription, "language", "en") or "en",
        }
        duration = getattr(transcription, "duration", None)
        if duration is not None:
            result["duration"] = duration

        logger.debug(
            "speech_service: transcribed %d bytes → %d chars (model=%s lang=%s)",
            len(audio_bytes),
            len(result["text"]),
            model,
            result["language"],
        )
        return result

    except Exception as exc:
        logger.error("speech_service: transcription failed: %s", exc)
        return _EMPTY
