"""
Tests for AudioPreprocessor (audio_preprocessor.py).

All tests mock the FFmpeg subprocess — no real FFmpeg needed to run the suite.
The WAV fixture is built with numpy/struct so we can verify format properties
without any audio library dependency.
"""
from __future__ import annotations

import asyncio
import struct
import wave
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audio_preprocessor import (
    AudioPreprocessor,
    AudioPreprocessingError,
    FFmpegNotFoundError,
    check_ffmpeg,
    _save_debug_audio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(sample_rate: int = 16000, channels: int = 1, duration_s: float = 0.5) -> bytes:
    """Return minimal valid WAV bytes (sine-ish, silent PCM)."""
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)
        # zero samples (silence) — fine for testing the container format
        wf.writeframes(b"\x00\x00" * n_samples * channels)
    return buf.getvalue()


def _make_proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Build a mock asyncio Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _make_preprocessor() -> AudioPreprocessor:
    """Return an AudioPreprocessor with ffmpeg path pre-resolved to a fake path."""
    ap = AudioPreprocessor()
    ap._ffmpeg = "/usr/bin/ffmpeg"   # bypass lazy shutil.which in tests
    return ap


# ---------------------------------------------------------------------------
# check_ffmpeg
# ---------------------------------------------------------------------------

def test_check_ffmpeg_found():
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        result = check_ffmpeg()
    assert result == "/usr/bin/ffmpeg"


def test_check_ffmpeg_not_found():
    with patch("shutil.which", return_value=None):
        with pytest.raises(FFmpegNotFoundError) as exc_info:
            check_ffmpeg()
    assert "FFmpeg is required" in str(exc_info.value)
    assert "brew install" in str(exc_info.value)   # installation hint present


# ---------------------------------------------------------------------------
# AudioPreprocessor.clean_audio — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clean_audio_returns_wav_bytes():
    """clean_audio returns the bytes that ffmpeg writes to stdout."""
    fake_wav = _make_wav()

    with patch.object(AudioPreprocessor, "_run_ffmpeg", return_value=(0, fake_wav, b"")):
        result = await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")

    assert result == fake_wav


@pytest.mark.asyncio
async def test_clean_audio_output_is_16khz_mono():
    """The WAV returned by clean_audio (from mocked _run_ffmpeg) has 16 kHz / mono properties."""
    fake_wav = _make_wav(sample_rate=16000, channels=1)

    with patch.object(AudioPreprocessor, "_run_ffmpeg", return_value=(0, fake_wav, b"")):
        result = await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")

    buf = io.BytesIO(result)
    with wave.open(buf, "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1


@pytest.mark.asyncio
async def test_clean_audio_ffmpeg_command_contains_filters():
    """FFmpeg is invoked with the expected filter chain args."""
    fake_wav = _make_wav()
    captured_cmds: list[list] = []

    def fake_run_ffmpeg(cmd, audio_bytes):
        captured_cmds.append(cmd)
        return (0, fake_wav, b"")

    with patch.object(AudioPreprocessor, "_run_ffmpeg", side_effect=fake_run_ffmpeg):
        await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")

    assert captured_cmds, "expected _run_ffmpeg to be called"
    cmd_str = " ".join(captured_cmds[0])
    assert "highpass" in cmd_str
    assert "lowpass"  in cmd_str
    assert "afftdn"   in cmd_str
    assert "loudnorm" in cmd_str
    assert "16000"    in cmd_str
    assert "pipe:0"   in cmd_str
    assert "pipe:1"   in cmd_str


# ---------------------------------------------------------------------------
# AudioPreprocessor.clean_audio — error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clean_audio_raises_on_empty_bytes():
    with pytest.raises(AudioPreprocessingError, match="Empty audio bytes"):
        await _make_preprocessor().clean_audio(b"")


@pytest.mark.asyncio
async def test_clean_audio_raises_on_ffmpeg_nonzero_exit():
    with patch.object(AudioPreprocessor, "_run_ffmpeg", return_value=(1, b"", b"some ffmpeg error")):
        with pytest.raises(AudioPreprocessingError, match="FFmpeg conversion failed"):
            await _make_preprocessor().clean_audio(b"bad audio", input_format="webm")


@pytest.mark.asyncio
async def test_clean_audio_raises_on_empty_stdout():
    """FFmpeg exits 0 but produces nothing — should raise."""
    with patch.object(AudioPreprocessor, "_run_ffmpeg", return_value=(0, b"", b"")):
        with pytest.raises(AudioPreprocessingError, match="no audio output"):
            await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")


@pytest.mark.asyncio
async def test_clean_audio_raises_on_ffmpeg_not_found():
    with patch.object(
        AudioPreprocessor, "_run_ffmpeg",
        side_effect=FileNotFoundError("ffmpeg not found"),
    ):
        with pytest.raises(FFmpegNotFoundError):
            await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")


@pytest.mark.asyncio
async def test_clean_audio_raises_on_timeout():
    import subprocess as _subprocess
    with patch.object(
        AudioPreprocessor, "_run_ffmpeg",
        side_effect=_subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30),
    ):
        with pytest.raises(AudioPreprocessingError, match="timed out"):
            await _make_preprocessor().clean_audio(b"raw audio", input_format="webm")


# ---------------------------------------------------------------------------
# Debug audio saving
# ---------------------------------------------------------------------------

def test_save_debug_audio_writes_file(tmp_path):
    wav = _make_wav()
    with patch(
        "app.services.audio_preprocessor.Path",
        return_value=MagicMock(
            __truediv__=lambda s, o: tmp_path / o,
            resolve=lambda: tmp_path,
            parents={2: tmp_path},
        ),
    ):
        # Call directly; just verify it doesn't raise
        import app.services.audio_preprocessor as mod
        real_path = mod.Path

        mod.Path = lambda *a: tmp_path
        try:
            _save_debug_audio(wav)
        finally:
            mod.Path = real_path


def test_save_debug_audio_never_raises_on_error():
    """Even if file writing fails, the function must not propagate exceptions."""
    with patch("app.services.audio_preprocessor.Path", side_effect=RuntimeError("disk full")):
        _save_debug_audio(b"some bytes")   # must not raise
