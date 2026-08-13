"""
Audio Preprocessor — Phase 5

Cleans raw browser audio bytes before sending them to Whisper.

Pipeline:
    Browser audio
        ↓
    FFmpeg
        ↓
    16 kHz mono PCM WAV
        ↓
    High-pass filter
        ↓
    Low-pass filter
        ↓
    FFT denoising
        ↓
    Loudness normalization
        ↓
    faster-whisper

Windows compatibility:
    FFmpeg is executed with subprocess.run() inside
    asyncio.to_thread() instead of asyncio.create_subprocess_exec().

This avoids the NotImplementedError that can occur with
asyncio subprocesses on Windows/Python 3.13.

Public interface:
    preprocessor = AudioPreprocessor()

    cleaned_wav = await preprocessor.clean_audio(
        raw_bytes,
        input_format="webm"
    )

FFmpeg is required as a system dependency.
Call check_ffmpeg() during application startup.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import time
from pathlib import Path

from app.config import get_settings


logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class FFmpegNotFoundError(RuntimeError):
    """Raised when FFmpeg cannot be found on the system PATH."""

    pass


class AudioPreprocessingError(RuntimeError):
    """Raised when audio preprocessing fails."""

    pass


# ============================================================================
# FFMPEG CHECK
# ============================================================================


def check_ffmpeg() -> str:
    """
    Verify that FFmpeg is available on PATH.

    Returns:
        Resolved FFmpeg executable path.

    Raises:
        FFmpegNotFoundError:
            If FFmpeg is not available.
    """

    path = shutil.which("ffmpeg")

    if not path:
        raise FFmpegNotFoundError(
            "FFmpeg is required for audio preprocessing but was not found. "
            "Install it with:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: winget install Gyan.FFmpeg\n"
            "Then restart your terminal/IDE and make sure 'ffmpeg' is on PATH."
        )

    logger.info(
        "audio_preprocessor: ffmpeg found at %s",
        path,
    )

    return path


# ============================================================================
# AUDIO PREPROCESSOR
# ============================================================================


class AudioPreprocessor:
    """
    Stateless audio cleaning helper.

    Safe to use as a module-level singleton.

    FFmpeg runs inside a worker thread so that expensive/synchronous
    subprocess execution does not block FastAPI's async event loop.
    """

    def __init__(self) -> None:
        # Resolve lazily so PATH changes are picked up.
        self._ffmpeg: str | None = None

    # ------------------------------------------------------------------------
    # FFMPEG RESOLUTION
    # ------------------------------------------------------------------------

    def _get_ffmpeg(self) -> str:
        """
        Resolve the FFmpeg executable.

        Returns:
            Path to FFmpeg executable.

        Raises:
            FFmpegNotFoundError:
                If FFmpeg is not available.
        """

        if self._ffmpeg is None:
            path = shutil.which("ffmpeg")

            if not path:
                raise FFmpegNotFoundError(
                    "FFmpeg is required for audio preprocessing but was not found."
                )

            self._ffmpeg = path

        return self._ffmpeg

    # ------------------------------------------------------------------------
    # SYNCHRONOUS FFMPEG EXECUTION
    # ------------------------------------------------------------------------

    def _run_ffmpeg(
        self,
        cmd: list[str],
        audio_bytes: bytes,
    ) -> tuple[int, bytes, bytes]:
        """
        Execute FFmpeg synchronously.

        IMPORTANT:
        This method is NOT called directly from the async event loop.

        clean_audio() calls this using:

            asyncio.to_thread(...)

        This avoids Windows/Python 3.13 issues with:

            asyncio.create_subprocess_exec()
        """

        result = subprocess.run(
            cmd,
            input=audio_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30.0,
            check=False,
            shell=False,
        )

        return (
            result.returncode,
            result.stdout,
            result.stderr,
        )

    # ------------------------------------------------------------------------
    # AUDIO CLEANING
    # ------------------------------------------------------------------------

    # Formats that require a seekable input file (moov atom at end of file).
    # These CANNOT be reliably demuxed from a non-seekable stdin pipe.
    _SEEKABLE_FORMATS = frozenset({"mp4", "mov", "mkv", "avi", "m4a", "m4v"})

    async def clean_audio(
        self,
        audio_bytes: bytes,
        input_format: str = "webm",
    ) -> bytes:
        """
        Preprocess raw audio/video bytes and return cleaned 16 kHz mono WAV.

        Parameters:
            audio_bytes:
                Raw bytes — either a browser WebM/OGG chunk (live lecture)
                or a full MP4/MKV video file downloaded from Cloudinary.

            input_format:
                Container hint: "mp4", "webm", "ogg", "wav", etc.
                MP4/MKV/MOV/AVI are written to a temp file before FFmpeg
                runs, because those containers require seekable access.
                All other formats are piped via stdin.

        Returns:
            16 kHz mono PCM WAV bytes.

        Raises:
            AudioPreprocessingError: FFmpeg processing failed.
            FFmpegNotFoundError:     FFmpeg not found on PATH.
        """

        if not audio_bytes:
            raise AudioPreprocessingError("Empty audio bytes received")

        settings = get_settings()
        t_start = time.monotonic()

        logger.debug(
            "audio_preprocessor: preprocessing %d bytes (format=%s)",
            len(audio_bytes), input_format,
        )

        # --------------------------------------------------------------------
        # Build FFmpeg filter chain
        # --------------------------------------------------------------------

        filter_chain = (
            f"highpass=f={settings.AUDIO_HIGHPASS},"
            f"lowpass=f={settings.AUDIO_LOWPASS},"
            f"afftdn="
            f"nr={settings.AUDIO_NOISE_REDUCTION}:"
            f"nf={settings.AUDIO_NOISE_FLOOR},"
            f"loudnorm"
        )

        ffmpeg_bin = self._get_ffmpeg()

        # --------------------------------------------------------------------
        # Choose input strategy
        #
        # MP4, MKV, MOV, AVI store their index (moov atom) at the end of the
        # file. FFmpeg's demuxer for these formats REQUIRES seekable access —
        # it cannot parse them from a non-seekable stdin pipe. Reading via
        # pipe produces an empty or corrupt audio stream.
        #
        # Fix: write those formats to a NamedTemporaryFile first, then pass
        # the file path to FFmpeg. Every other format (WebM, OGG, WAV, MP3,
        # FLAC) streams fine via pipe:0.
        # --------------------------------------------------------------------

        use_tempfile = input_format.lower() in self._SEEKABLE_FORMATS

        if use_tempfile:
            import tempfile, os as _os

            def _run_with_tempfile() -> tuple[int, bytes, bytes]:
                suffix = f".{input_format.lower()}"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                try:
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-i", tmp_path,
                        "-af", filter_chain,
                        "-ar", str(settings.AUDIO_SAMPLE_RATE),
                        "-ac", str(settings.AUDIO_CHANNELS),
                        "-f", "wav",
                        "-acodec", "pcm_s16le",
                        "pipe:1",
                    ]
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=120.0,
                        check=False,
                        shell=False,
                    )
                    return result.returncode, result.stdout, result.stderr
                finally:
                    try:
                        _os.unlink(tmp_path)
                    except OSError:
                        pass

            try:
                returncode, stdout, stderr = await asyncio.to_thread(_run_with_tempfile)
            except Exception as exc:
                raise AudioPreprocessingError(
                    f"FFmpeg tempfile error: {type(exc).__name__}: {exc}"
                ) from exc
        else:
            # Streamable formats — pipe via stdin as before
            cmd = [
                ffmpeg_bin, "-y",
                "-f", input_format,
                "-i", "pipe:0",
                "-af", filter_chain,
                "-ar", str(settings.AUDIO_SAMPLE_RATE),
                "-ac", str(settings.AUDIO_CHANNELS),
                "-f", "wav",
                "-acodec", "pcm_s16le",
                "pipe:1",
            ]
            try:
                returncode, stdout, stderr = await asyncio.to_thread(
                    self._run_ffmpeg, cmd, audio_bytes,
                )
            except subprocess.TimeoutExpired as exc:
                raise AudioPreprocessingError("FFmpeg timed out after 30 seconds") from exc
            except FileNotFoundError as exc:
                self._ffmpeg = None
                raise FFmpegNotFoundError(
                    f"FFmpeg executable not found at '{ffmpeg_bin}'."
                ) from exc
            except (PermissionError, OSError) as exc:
                raise AudioPreprocessingError(f"OS error starting FFmpeg: {exc}") from exc
            except Exception as exc:
                raise AudioPreprocessingError(
                    f"FFmpeg subprocess error: {type(exc).__name__}: {exc}"
                ) from exc

        # --------------------------------------------------------------------
        # Check FFmpeg return code
        # --------------------------------------------------------------------

        if returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error("audio_preprocessor: FFmpeg exited with code %d\nstderr:\n%s",
                         returncode, err_msg)
            raise AudioPreprocessingError(
                f"FFmpeg conversion failed (exit {returncode}): {err_msg[:500]}"
            )

        if not stdout or len(stdout) < 12:
            raise AudioPreprocessingError("FFmpeg produced empty or invalid WAV output")

        if stdout[0:4] != b"RIFF" or stdout[8:12] != b"WAVE":
            logger.warning("audio_preprocessor: output does not appear to be a standard WAV file")

        elapsed = time.monotonic() - t_start
        logger.debug(
            "audio_preprocessor: preprocessing completed in %.2f s (%d -> %d bytes)",
            elapsed, len(audio_bytes), len(stdout),
        )

        if getattr(settings, "SAVE_DEBUG_AUDIO", False):
            _save_debug_audio(stdout)

        return stdout


# ============================================================================
# DEBUG AUDIO
# ============================================================================


def _save_debug_audio(wav_bytes: bytes) -> None:
    """
    Save cleaned WAV for local debugging.

    Enabled only when:

        SAVE_DEBUG_AUDIO=true

    Debug files should never be committed.
    """

    try:

        debug_dir = (
            Path(__file__)
            .resolve()
            .parents[2]
            / "debug_audio"
        )

        debug_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = int(
            time.time() * 1000
        )

        path = (
            debug_dir
            / f"chunk_{timestamp}.wav"
        )

        path.write_bytes(wav_bytes)

        logger.debug(
            "audio_preprocessor: debug audio saved → %s",
            path,
        )

    except Exception as exc:

        # Debug functionality must never break
        # the actual audio pipeline.

        logger.warning(
            "audio_preprocessor: "
            "could not save debug audio: %s",
            exc,
        )


# ============================================================================
# MODULE-LEVEL SINGLETON
# ============================================================================

preprocessor = AudioPreprocessor()