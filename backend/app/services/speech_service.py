"""
Speech service — Phase 5

Pipeline:
    audio_bytes (raw browser WebM/OGG/…)
        ↓
    AudioPreprocessor.clean_audio()  — FFmpeg: mono 16 kHz, highpass, lowpass,
                                       moderate denoising, loudnorm
        ↓
    cleaned WAV bytes
        ↓
    Groq Whisper API  (whisper-large-v3-turbo or whisper-large-v3)
        ↓
    transcript dict

Public interface
----------------
    result = await transcribe_audio(audio_bytes, filename="chunk.webm")

Returns:
    {
        "text":     "Hello, this is the transcribed speech.",
        "language": "en",
        "duration": 4.32,   # only when present in the API response
    }

If the API key is missing, or if any step fails, an empty result is returned
so the WebSocket handler can continue without crashing.
"""
import io
import logging

from app.config import get_settings
from app.integrations.groq_service import get_groq_client
from app.services.audio_preprocessor import (
    AudioPreprocessor,
    AudioPreprocessingError,
    FFmpegNotFoundError,
    preprocessor as _default_preprocessor,
)

logger = logging.getLogger(__name__)

# Groq's available Whisper models
WHISPER_TURBO = "whisper-large-v3-turbo"
WHISPER_LARGE = "whisper-large-v3"

_EMPTY: dict = {"text": "", "language": "en"}


def _choose_model() -> str:
    """
    Pick the Whisper model from settings.WHISPER_MODEL.
    Accepts the short alias 'turbo' / 'large' or the full model name.
    Falls back to whisper-large-v3-turbo.
    """
    alias = get_settings().WHISPER_MODEL.lower().strip()
    if alias in ("large", WHISPER_LARGE):
        return WHISPER_LARGE
    return WHISPER_TURBO


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language: str | None = None,
    prompt: str | None = None,
    _preprocessor: AudioPreprocessor | None = None,
) -> dict:
    """
    Preprocess *audio_bytes* then transcribe via the Groq Whisper API.

    Parameters
    ----------
    audio_bytes   : raw audio from the browser (any format FFmpeg can decode)
    filename      : container hint forwarded to the Groq API
    language      : ISO-639-1 hint (e.g. "en", "hi"); None → auto-detect.
                    Falls back to WHISPER_LANGUAGE env var if set.
    prompt        : optional preceding context to improve accuracy
    _preprocessor : injected in tests; uses the module singleton by default

    Returns
    -------
    dict with keys ``text`` (str), ``language`` (str), optionally ``duration`` (float).
    """
    if not audio_bytes:
        return _EMPTY

    settings = get_settings()

    if not settings.GROQ_API_KEY:
        logger.warning("speech_service: GROQ_API_KEY is not set — returning empty transcript")
        return _EMPTY

    # ── 1. Determine language ──────────────────────────────────────────────
    effective_language = language or settings.WHISPER_LANGUAGE or None

    # ── 2. Preprocess audio ────────────────────────────────────────────────
    logger.debug("speech_service: received audio chunk (%d bytes)", len(audio_bytes))

    proc = _preprocessor or _default_preprocessor

    # Derive the FFmpeg input format from the filename extension
    input_format = _format_from_filename(filename)

    logger.debug("speech_service: preprocessing audio (format=%s)", input_format)
    try:
        cleaned_bytes = await proc.clean_audio(audio_bytes, input_format=input_format)
    except (AudioPreprocessingError, FFmpegNotFoundError) as exc:
        logger.error("speech_service: audio preprocessing failed: %s", exc, exc_info=True)
        return _EMPTY
    except Exception as exc:
        logger.error("speech_service: unexpected preprocessing error: %s", exc, exc_info=True)
        return _EMPTY

    logger.debug("speech_service: audio preprocessing completed (%d bytes WAV)", len(cleaned_bytes))

    # ── 3. Transcribe cleaned WAV ──────────────────────────────────────────
    model = _choose_model()
    client = get_groq_client()

    logger.debug("speech_service: transcribing audio (model=%s)", model)
    try:
        # Always send as WAV after preprocessing
        file_tuple = ("audio.wav", io.BytesIO(cleaned_bytes))

        kwargs: dict = dict(
            file=file_tuple,
            model=model,
            response_format="verbose_json",
        )
        if effective_language:
            kwargs["language"] = effective_language
        if prompt:
            kwargs["prompt"] = prompt

        transcription = await client.audio.transcriptions.create(**kwargs)

        text = (transcription.text or "").strip()
        language = getattr(transcription, "language", "en") or "en"
        result: dict = {"text": text, "language": language}

        duration = getattr(transcription, "duration", None)
        if duration is not None:
            result["duration"] = duration

        # Extract per-segment timestamps from verbose_json response.
        # Each segment: {"start": float, "end": float, "text": str}
        raw_segments = getattr(transcription, "segments", None) or []
        segments = []
        for seg in raw_segments:
            try:
                seg_start = float(getattr(seg, "start", 0.0))
                seg_end = float(getattr(seg, "end", seg_start + 3.0))
                seg_text = (getattr(seg, "text", "") or "").strip()
                if seg_text:
                    segments.append({"start": seg_start, "end": seg_end, "text": seg_text})
            except (TypeError, ValueError):
                continue
        if segments:
            result["segments"] = segments

        logger.debug(
            "speech_service: whisper transcription completed — %d chars %d segments (lang=%s model=%s)",
            len(text),
            len(segments),
            language,
            model,
        )
        return result

    except Exception as exc:
        logger.error("speech_service: transcription failed: %s", exc, exc_info=True)
        return _EMPTY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_from_filename(filename: str) -> str:
    """
    Map a filename extension to an FFmpeg input format string.
    Falls back to 'webm' (most common browser MediaRecorder output).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "webm": "webm",
        "ogg":  "ogg",
        "mp4":  "mp4",
        "m4a":  "mp4",
        "wav":  "wav",
        "mp3":  "mp3",
        "flac": "flac",
    }.get(ext, "webm")
