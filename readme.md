# VidyaRoom

> AI-powered lecture platform — live transcription, translation, notes, doubt resolution, and teacher analytics in one place.

VidyaRoom turns a recorded lecture into a full interactive learning experience. Teachers upload a video, the backend pipeline transcribes, translates, detects topics and key moments, and generates notes automatically. Students watch the lecture with live transcript and translation panels, ask the AI chatbot questions, raise doubts to the teacher, and rate the lecture. Teachers get a rich analytics dashboard covering engagement, ratings, doubts, and a composite performance score.

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Environment Variables](#environment-variables)
7. [Getting Started](#getting-started)
8. [Database Migrations](#database-migrations)
9. [API Reference](#api-reference)
10. [Frontend Pages](#frontend-pages)
11. [Running Tests](#running-tests)

---

## Features

### For Students
- **Lecture browser** — browse and open completed lectures
- **Video player** — watch lectures with playback analytics collected silently in the background (play, pause, seek, rewind, replay counters + watch time + completion %)
- **Live transcript** — timestamped speech-to-text panel synced to playback
- **Live translation** — real-time translation panel (default target: Hindi)
- **Topic tracker** — auto-detected topic and subtopic displayed as the lecture progresses
- **Important events** — key lecture moments flagged by the AI
- **Lecture notes** — auto-generated markdown notes, downloadable as PDF, filterable by language
- **AI chatbot** — lecture-grounded question answering; each student has their own private chat thread
- **Doubts** — send doubts directly to the teacher; read teacher replies in real time
- **Ratings** — submit a 1–5 star rating with optional written feedback

### For Teachers
- **Lecture management** — create, list, and manage lectures; mark them as completed
- **Video upload** — upload MP4/MOV/WebM/MKV/AVI (max 500 MB) directly to Cloudinary
- **Pipeline trigger** — start the AI processing pipeline for any uploaded lecture
- **Doubts dashboard** — view and reply to all student doubt threads across all lectures
- **Analytics dashboard** — composite teacher performance score (0–5) composed of:
  - Average star rating sub-score
  - Doubt response rate sub-score
  - Video engagement sub-score
- **Engagement stats** — total views, average watch time, average completion %, play/pause/seek/rewind/replay/forward counts, timeline heatmap of frequently revisited segments
- **Rating analytics** — distribution of 1–5 stars, written reviews (anonymised)
- **Topic breakdown** — per-topic question counts and engagement details
- **Problem-solving stats** — doubt volume, response rate, open vs. resolved counts
- **Feedback overview** — all of the above combined in one API call

### AI Pipeline (per lecture)
1. Download audio from Cloudinary
2. Transcribe via **Groq Whisper** (verbose JSON with per-segment timestamps)
3. Group Whisper segments into ~5-second windows
4. For each window, concurrently:
   - Persist `speech_event` to database
   - Translate via **Google Gemini**
   - Detect current topic / subtopic via **Groq LLM**
   - Detect important events via **Groq LLM**
5. Generate full lecture notes once from the complete transcript
6. Mark lecture as completed and broadcast `done` over WebSocket

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15, React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.13, SQLAlchemy 2 (async), Pydantic v2 |
| **Database** | PostgreSQL (Neon or any Postgres instance) |
| **Migrations** | Alembic |
| **Auth** | HTTP-only session cookies, bcrypt password hashing |
| **Speech-to-text** | Groq Whisper (`whisper-large-v3-turbo` or `whisper-large-v3`) |
| **Translation** | Google Gemini (`gemini-2.5-flash-lite`) |
| **LLM inference** | Groq (`llama-3.1-8b-instant` or configurable) |
| **Video storage** | Cloudinary |
| **Audio processing** | FFmpeg (via Python subprocess) |
| **Real-time** | WebSockets (FastAPI + `websockets`) |
| **PDF export** | jsPDF (frontend) |
| **Markdown rendering** | react-markdown + remark-gfm |

---

## Architecture

```
Student / Teacher Browser
        │
        │  HTTP / WebSocket
        ▼
   Next.js 15 (port 3000)
        │
        │  REST API / WebSocket
        ▼
   FastAPI (port 8000)
   ┌─────────────────────────────────────────┐
   │  Routers                                │
   │    /api/auth      Authentication        │
   │    /lectures      Lectures + Events     │
   │    /lectures      Chat + Doubts         │
   │    /api/feedback  Analytics             │
   │    /ws            WebSocket             │
   │                                         │
   │  Services                               │
   │    lecture_pipeline   AI processing     │
   │    speech_service     Groq Whisper      │
   │    chatbot_service    Groq LLM          │
   │    feedback_service   Analytics         │
   │    playback_service   Engagement        │
   │    rating_service     Star ratings      │
   │    chat_service       Doubt threads     │
   │    note_service       Lecture notes     │
   │    audio_preprocessor FFmpeg            │
   │    vision_service     OpenCV / OCR      │
   └──────────────────┬──────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      PostgreSQL   Cloudinary   Groq / Gemini
```

---

## Project Structure

```
vidyaroom/
├── backend/
│   ├── alembic/
│   │   └── versions/          # Migration files (0001 → 0006)
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py        # POST /api/auth/signup|login|logout, GET /api/auth/me
│   │   │   ├── chat.py        # Student AI chat + teacher doubt threads
│   │   │   ├── feedback.py    # Teacher analytics + student ratings + playback flush
│   │   │   ├── lectures.py    # Lecture CRUD, video upload, pipeline trigger
│   │   │   ├── qa.py          # Q&A endpoint (stub)
│   │   │   └── websocket.py   # /ws/lectures/{lecture_id}
│   │   ├── database/
│   │   │   ├── database.py    # Async engine + session factory
│   │   │   └── models.py      # SQLAlchemy ORM models
│   │   ├── graph/             # LangGraph agent graphs (live + notes)
│   │   ├── integrations/
│   │   │   ├── cloudinary_service.py
│   │   │   ├── gemini_service.py
│   │   │   └── groq_service.py
│   │   ├── schemas/           # Pydantic request / response schemas
│   │   ├── services/          # Business logic layer
│   │   │   ├── lecture_pipeline.py   # Full AI processing pipeline
│   │   │   ├── playback_service.py   # Engagement analytics upsert + aggregation
│   │   │   ├── feedback_service.py   # Teacher analytics aggregation
│   │   │   ├── rating_service.py     # Star ratings
│   │   │   ├── chat_service.py       # Doubt threads
│   │   │   ├── chatbot_service.py    # AI chatbot
│   │   │   └── ...
│   │   ├── config.py          # Pydantic settings (reads .env)
│   │   └── main.py            # FastAPI app, CORS, router mounting
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── app/
    │   ├── page.tsx            # Landing / redirect
    │   ├── login/page.tsx
    │   ├── signup/page.tsx
    │   ├── student/
    │   │   ├── dashboard/      # Student home
    │   │   ├── lectures/       # Lecture list
    │   │   ├── lectures/[lectureId]/  # Lecture viewer
    │   │   ├── notes/          # All notes
    │   │   ├── doubts/         # All doubts
    │   │   └── bookmarks/
    │   └── teacher/
    │       ├── dashboard/      # Teacher home + performance score
    │       ├── lectures/       # Lecture list + pipeline controls
    │       ├── lectures/[lectureId]/doubts/  # Per-lecture doubt viewer
    │       ├── upload/         # Video upload
    │       ├── notes/          # All notes
    │       ├── doubts/         # All doubt threads
    │       └── feedback/       # Full analytics dashboard
    ├── components/
    │   ├── layout/             # AppShell, AppHeader, AppSidebar, PageContainer
    │   ├── lecture/            # All lecture-scoped panels and cards
    │   └── ui/                 # Button, Card, Badge, Input, ProgressBar, Avatar
    ├── hooks/                  # useAuth and other custom hooks
    ├── lib/
    │   └── api.ts              # Typed API client (wraps fetch)
    ├── types/                  # TypeScript interfaces
    └── .env.local.example
```

---

## Prerequisites

Install these before running anything:

| Dependency | Version | Notes |
|---|---|---|
| Node.js | ≥ 18 | For the Next.js frontend |
| Python | 3.11+ | For the FastAPI backend |
| FFmpeg | any recent | Required for audio preprocessing. See install notes below. |
| Tesseract OCR | any recent | Required for OCR / frame extraction. See install notes below. |
| PostgreSQL | 14+ | Or use a managed service like Neon |

**FFmpeg install:**
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

**Tesseract install:**
```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt install tesseract-ocr

# Windows — download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki
```

---

## Environment Variables

### Backend — `backend/.env`

Copy `backend/.env.example` to `backend/.env` and fill in every value.

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string. Use `postgresql+psycopg://` prefix for async driver, or plain `postgresql://` / `postgres://` (auto-converted). |
| `GROQ_API_KEY` | ✅ | Groq API key for Whisper transcription and LLM inference. Get one at [console.groq.com](https://console.groq.com). |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for translation. Get one at [aistudio.google.com](https://aistudio.google.com). |
| `CLOUD_NAME` | ✅ | Cloudinary cloud name for video storage. |
| `CLOUD_API_KEY` | ✅ | Cloudinary API key. |
| `CLOUD_API_SECRET` | ✅ | Cloudinary API secret. |
| `SECRET_KEY` | ✅ | Secret for signing session tokens. Use a long random string in production. |
| `CORS_ORIGINS` | ✅ | Comma-separated list of allowed frontend origins, e.g. `http://localhost:3000`. |
| `GROQ_MODEL` | — | Groq chat model. Default: `llama-3.1-8b-instant`. |
| `GEMINI_TRANSLATION_MODEL` | — | Gemini model for translation. Default: `gemini-2.5-flash-lite`. |
| `WHISPER_MODEL` | — | `turbo` (faster) or `large` (most accurate). Default: `turbo`. |
| `WHISPER_LANGUAGE` | — | ISO-639-1 language hint for Whisper. Leave blank for auto-detect. |
| `TARGET_LANGUAGE` | — | Translation target language code. Default: `hi` (Hindi). |
| `AUDIO_SAMPLE_RATE` | — | FFmpeg output sample rate in Hz. Default: `16000`. |
| `AUDIO_CHANNELS` | — | FFmpeg output channels. Default: `1` (mono). |
| `AUDIO_HIGHPASS` | — | High-pass filter cutoff (Hz). Default: `100`. |
| `AUDIO_LOWPASS` | — | Low-pass filter cutoff (Hz). Default: `8000`. |
| `AUDIO_NOISE_REDUCTION` | — | afftdn `nr=` value (0–97). Default: `12`. |
| `AUDIO_NOISE_FLOOR` | — | afftdn `nf=` value (dBFS). Default: `-40`. |
| `SAVE_DEBUG_AUDIO` | — | Set `true` to save cleaned audio chunks to `backend/debug_audio/`. Default: `false`. |
| `TOPIC_DETECTION_INTERVAL_SECONDS` | — | Min seconds between topic detection calls per lecture. Default: `30`. |
| `IMPORTANT_EVENT_INTERVAL_SECONDS` | — | Min seconds between important-event detection calls per lecture. Default: `30`. |
| `MAX_TRANSLATION_CONTEXT_CHARS` | — | Max chars sent to Gemini per translation call. Default: `4000`. |
| `MAX_TOPIC_CONTEXT_CHARS` | — | Max chars sent to Groq per topic call. Default: `5000`. |
| `MAX_EVENT_CONTEXT_CHARS` | — | Max chars sent to Groq per event call. Default: `5000`. |
| `MAX_CONCURRENT_GROQ_REQUESTS` | — | Semaphore cap on simultaneous Groq requests. Default: `1`. |
| `GROQ_MAX_RETRIES` | — | Max retry attempts on Groq 429 rate-limit errors. Default: `2`. |
| `MIN_TRANSCRIPT_CHARS` | — | Min transcript length to bother calling Groq. Default: `10`. |

### Frontend — `frontend/.env.local`

Copy `frontend/.env.local.example` to `frontend/.env.local`.

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend REST API base URL. |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Backend WebSocket base URL. |

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd vidyaroom
```

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your DATABASE_URL, API keys, etc.

# Apply database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and fill in environment variables
cp .env.local.example .env.local
# Defaults (http://localhost:8000) work for local development

# Start the development server
npm run dev
```

The app will be available at `http://localhost:3000`.

---

## Database Migrations

All schema changes are managed by Alembic. **Never call `Base.metadata.create_all()` manually.**

```bash
# From the backend/ directory

# Check current migration state
alembic current

# View full migration history
alembic history

# Apply all pending migrations (run this after every pull)
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Generate a new migration after changing models.py
alembic revision --autogenerate -m "describe the change"
```

### Migration history

| Revision | Description |
|---|---|
| `0001` | Baseline schema — users, lectures, lecture_events, notes |
| `0002` | Add `video_url` to lectures |
| `0003` | Add AI fields to chat messages |
| `0004` | Add `message_type` to chat messages |
| `0005` | Add `lecture_ratings` table |
| `0006` | Add `playback_analytics` table |

---

## API Reference

All endpoints are prefixed with the origin (`http://localhost:8000`).  
Interactive Swagger UI is available at `/docs`.

### Authentication — `/api/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/signup` | None | Create account; sets session cookie |
| `POST` | `/api/auth/login` | None | Exchange credentials for session cookie |
| `POST` | `/api/auth/logout` | Cookie | Clear session cookie |
| `GET` | `/api/auth/me` | Cookie | Return current user |

### Lectures — `/lectures`

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/lectures` | None | List all lectures |
| `POST` | `/lectures/start` | Optional | Create a new lecture session |
| `GET` | `/lectures/teacher/lectures` | Teacher | List lectures owned by the teacher |
| `GET` | `/lectures/student/lectures` | Student | List completed lectures |
| `GET` | `/lectures/student/lectures/{id}` | Student | Get one completed lecture |
| `POST` | `/lectures/{id}/video` | Teacher | Upload lecture video (max 500 MB) |
| `POST` | `/lectures/{id}/process` | None | Start AI processing pipeline |
| `POST` | `/lectures/{id}/complete` | None | Mark lecture as completed |
| `GET` | `/lectures/{id}` | None | Get lecture by ID |
| `GET` | `/lectures/{id}/events` | None | List lecture events (optional `?type=`) |
| `GET` | `/lectures/{id}/notes` | None | Get lecture notes (optional `?language=`) |

### Chat & Doubts — `/lectures`

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/lectures/{id}/chat` | Student | Get student's AI chat history |
| `POST` | `/lectures/{id}/chat` | Student | Ask the AI chatbot |
| `GET` | `/lectures/{id}/doubts` | Student | Get student's doubt thread |
| `POST` | `/lectures/{id}/doubts` | Student | Post a doubt to the teacher |
| `GET` | `/lectures/teacher/{id}/chat` | Teacher | View all student doubt threads |
| `POST` | `/lectures/teacher/{id}/chat/{thread_id}` | Teacher | Reply to a student doubt |
| `GET` | `/lectures/teacher/{id}/chat/analytics` | Teacher | Doubt analytics for a lecture |

### Feedback & Analytics — `/api/feedback`

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/feedback/overview` | Teacher | Full feedback overview (all or `?lecture_id=`) |
| `GET` | `/api/feedback/topics` | Teacher | Per-topic breakdown |
| `GET` | `/api/feedback/lectures/{id}` | Teacher | Overview scoped to one lecture |
| `GET` | `/api/feedback/lectures/{id}/ratings/analytics` | Teacher | Star rating distribution |
| `GET` | `/api/feedback/lectures/{id}/ratings/reviews` | Teacher | Written reviews (anonymised) |
| `GET` | `/api/feedback/engagement` | Teacher | Playback engagement stats (all or `?lecture_id=`) |
| `GET` | `/api/feedback/problem-solving` | Teacher | Doubt response analytics |
| `GET` | `/api/feedback/teacher-score` | Teacher | Composite performance score (0–5) |
| `GET` | `/api/feedback/lectures/{id}/rating` | Any | Student's own rating for a lecture |
| `POST` | `/api/feedback/lectures/{id}/rating` | Student | Submit a star rating |
| `PUT` | `/api/feedback/lectures/{id}/rating` | Student | Update existing rating |
| `POST` | `/api/feedback/lectures/{id}/playback` | Student | Flush batched video playback events |

### WebSocket — `/ws`

| Path | Description |
|---|---|
| `/ws/lectures/{lecture_id}` | Real-time lecture events broadcast (transcript, translation, topic updates, important events, pipeline status) |

### Health check

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok", "service": "vidyaroom"}` |

---

## Frontend Pages

| URL | Role | Description |
|---|---|---|
| `/` | Any | Landing page / redirect |
| `/login` | Any | Login form |
| `/signup` | Any | Sign-up form |
| `/student/dashboard` | Student | Student home |
| `/student/lectures` | Student | Browse completed lectures |
| `/student/lectures/[lectureId]` | Student | Full lecture viewer (video, transcript, translation, topics, notes, AI chat, doubts, rating) |
| `/student/notes` | Student | All notes across lectures |
| `/student/doubts` | Student | All doubt threads |
| `/student/bookmarks` | Student | Bookmarked items |
| `/teacher/dashboard` | Teacher | Home with performance score and lecture list |
| `/teacher/lectures` | Teacher | Manage lectures, trigger pipeline, upload video |
| `/teacher/lectures/[lectureId]/doubts` | Teacher | Reply to student doubts for one lecture |
| `/teacher/upload` | Teacher | Upload a new lecture video |
| `/teacher/notes` | Teacher | View generated notes |
| `/teacher/doubts` | Teacher | All doubt threads across all lectures |
| `/teacher/feedback` | Teacher | Full analytics dashboard |

---

## Running Tests

```bash
cd backend

# Activate virtual environment first (see Getting Started)

# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py -v
```

Tests use an isolated in-memory database via `conftest.py` fixtures — no production database is touched.
