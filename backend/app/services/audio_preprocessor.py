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

    async def clean_audio(
        self,
        audio_bytes: bytes,
        input_format: str = "webm",
    ) -> bytes:
        """
        Preprocess raw browser audio and return cleaned WAV bytes.

        Parameters:
            audio_bytes:
                Raw audio bytes received from browser.

            input_format:
                Browser/container format.

                Common values:
                    webm
                    ogg
                    mp4
                    wav

        Returns:
            16 kHz mono PCM WAV bytes.

        Raises:
            AudioPreprocessingError:
                If FFmpeg processing fails.

            FFmpegNotFoundError:
                If FFmpeg is unavailable.
        """

        # --------------------------------------------------------------------
        # Validate input
        # --------------------------------------------------------------------

        if not audio_bytes:
            raise AudioPreprocessingError(
                "Empty audio bytes received"
            )

        settings = get_settings()

        t_start = time.monotonic()

        logger.debug(
            "audio_preprocessor: preprocessing %d bytes "
            "(format=%s)",
            len(audio_bytes),
            input_format,
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

        # --------------------------------------------------------------------
        # Resolve FFmpeg
        # --------------------------------------------------------------------

        ffmpeg_bin = self._get_ffmpeg()

        # --------------------------------------------------------------------
        # FFmpeg command
        # --------------------------------------------------------------------

        cmd = [
            ffmpeg_bin,

            # Overwrite output if necessary
            "-y",

            # Input format from browser
            "-f",
            input_format,

            # Read audio from stdin
            "-i",
            "pipe:0",

            # Audio filters
            "-af",
            filter_chain,

            # Output sample rate
            "-ar",
            str(settings.AUDIO_SAMPLE_RATE),

            # Mono
            "-ac",
            str(settings.AUDIO_CHANNELS),

            # Output format
            "-f",
            "wav",

            # PCM 16-bit
            "-acodec",
            "pcm_s16le",

            # Write WAV to stdout
            "pipe:1",
        ]

        logger.debug(
            "audio_preprocessor: ffmpeg command prepared"
        )

        # --------------------------------------------------------------------
        # Run FFmpeg
        #
        # IMPORTANT:
        #
        # Do NOT use:
        #
        #     asyncio.create_subprocess_exec()
        #
        # because it can raise NotImplementedError on
        # Windows/Python 3.13 depending on the event loop.
        #
        # Instead:
        #
        #     asyncio.to_thread()
        #
        # runs subprocess.run() in a worker thread.
        # --------------------------------------------------------------------

        try:

            returncode, stdout, stderr = await asyncio.to_thread(
                self._run_ffmpeg,
                cmd,
                audio_bytes,
            )

        except subprocess.TimeoutExpired as exc:

            logger.error(
                "audio_preprocessor: FFmpeg timed out"
            )

            raise AudioPreprocessingError(
                "FFmpeg timed out after 30 seconds"
            ) from exc

        except FileNotFoundError as exc:

            # Reset cached path so the next request can resolve again.
            self._ffmpeg = None

            raise FFmpegNotFoundError(
                f"FFmpeg executable not found at '{ffmpeg_bin}'. "
                "Make sure FFmpeg is installed and available on PATH."
            ) from exc

        except PermissionError as exc:

            raise AudioPreprocessingError(
                "Permission denied while starting FFmpeg."
            ) from exc

        except OSError as exc:

            raise AudioPreprocessingError(
                f"Operating system error while starting FFmpeg: {exc}"
            ) from exc

        except Exception as exc:

            logger.exception(
                "audio_preprocessor: unexpected FFmpeg error"
            )

            raise AudioPreprocessingError(
                f"FFmpeg subprocess error: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # --------------------------------------------------------------------
        # Check FFmpeg return code
        # --------------------------------------------------------------------

        if returncode != 0:

            err_msg = stderr.decode(
                errors="replace"
            ).strip()

            logger.error(
                "audio_preprocessor: FFmpeg exited with code %d",
                returncode,
            )

            logger.error(
                "audio_preprocessor: FFmpeg stderr:\n%s",
                err_msg,
            )

            raise AudioPreprocessingError(
                "FFmpeg conversion failed "
                f"(exit {returncode}): "
                f"{err_msg[:500]}"
            )

        # --------------------------------------------------------------------
        # Validate output
        # --------------------------------------------------------------------

        if not stdout:

            raise AudioPreprocessingError(
                "FFmpeg produced no audio output"
            )

        # Basic WAV validation.
        #
        # WAV files normally begin with:
        #
        # RIFF....WAVE
        #
        if len(stdout) < 12:

            raise AudioPreprocessingError(
                "FFmpeg produced invalid WAV output"
            )

        if stdout[0:4] != b"RIFF" or stdout[8:12] != b"WAVE":

            logger.warning(
                "audio_preprocessor: output does not appear "
                "to be a standard WAV file"
            )

        # --------------------------------------------------------------------
        # Timing
        # --------------------------------------------------------------------

        elapsed = time.monotonic() - t_start

        logger.debug(
            "audio_preprocessor: preprocessing completed "
            "in %.2f seconds (%d → %d bytes)",
            elapsed,
            len(audio_bytes),
            len(stdout),
        )

        # --------------------------------------------------------------------
        # Optional debug audio
        # --------------------------------------------------------------------

        if getattr(settings, "SAVE_DEBUG_AUDIO", False):

            _save_debug_audio(stdout)

        # --------------------------------------------------------------------
        # Return cleaned WAV
        # --------------------------------------------------------------------

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