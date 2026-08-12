# VidyaRoom Backend

FastAPI backend for the VidyaRoom real-time lecture assistant.

## Quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — add DATABASE_URL and GROQ_API_KEY
uvicorn app.main:app --reload
```

Health check: http://localhost:8000/health

## System dependencies

### FFmpeg (required)

FFmpeg is used for audio preprocessing before Whisper transcription.
It must be installed on the system — it is **not** a Python package.

| Platform | Command |
|----------|---------|
| macOS    | `brew install ffmpeg` |
| Ubuntu / Debian | `sudo apt install ffmpeg` |
| Windows  | `winget install ffmpeg` or download from https://ffmpeg.org/download.html |

After installation verify with: `ffmpeg -version`

The server will fail to start with a clear error message if FFmpeg is missing.

## Audio pipeline

Every audio chunk received from the browser passes through a cleaning
pipeline before being sent to Groq Whisper:

```
Browser MediaRecorder (WebM/Opus)
  ↓
FastAPI WebSocket
  ↓
AudioPreprocessor  ──  FFmpeg subprocess
    ├── Decode any browser format (WebM, OGG, MP4 …)
    ├── Convert to mono 16 kHz PCM WAV
    ├── High-pass filter  (100 Hz) — removes AC hum / rumble
    ├── Low-pass filter  (8000 Hz) — removes hiss above speech
    ├── Moderate FFT denoising (afftdn nr=12 nf=-40)
    └── Loudness normalisation (loudnorm)
  ↓
Groq Whisper API  (whisper-large-v3-turbo)
  ↓
Transcript text
  ↓
LectureEvent → LangGraph pipeline
```

Preprocessing is intentionally moderate — it preserves speech quality and
does not aggressively strip noise.

## Configuration

Copy `.env.example` to `.env` and fill in the values:

```env
# Required
DATABASE_URL=postgresql+psycopg://user:pass@host/db
GROQ_API_KEY=gsk_...

# Whisper model
WHISPER_MODEL=turbo          # "turbo" (default) or "large"
WHISPER_LANGUAGE=            # ISO-639-1 hint, e.g. "en" — blank = auto-detect

# Audio preprocessing (FFmpeg)
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_HIGHPASS=100
AUDIO_LOWPASS=8000
AUDIO_NOISE_REDUCTION=12     # afftdn nr= (0–97); keep low to preserve speech
AUDIO_NOISE_FLOOR=-40        # afftdn nf= (dBFS)

# Debug: save cleaned audio chunks to backend/debug_audio/ (dev only)
SAVE_DEBUG_AUDIO=false
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | /health | Service health |
| POST | /lectures/start | Create a new lecture session |
| GET  | /lectures/{id} | Get lecture by ID |
| POST | /lectures/{id}/complete | Mark lecture complete |
| GET  | /lectures/{id}/events | List events (filterable by type) |
| GET  | /lectures/{id}/notes | List generated notes |
| POST | /lectures/{id}/questions | Ask a question (stub until Phase 9) |
| WS   | /ws/lectures/{id} | Real-time event stream |

## Running tests

```bash
pytest tests/ -v
```

All tests mock FFmpeg and the Groq API — no external services needed.
