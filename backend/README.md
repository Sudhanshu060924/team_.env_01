# VidyaRoom Backend

FastAPI backend for the VidyaRoom real-time lecture assistant.

## Quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Health check: http://localhost:8000/health

## Phase 1 endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Service health |
| GET | /api/lectures/ | List lectures (stub) |
| POST | /api/qa/ask | Ask a question (stub) |
| WS | /ws/{lecture_id} | Real-time events (stub) |

## Running tests

```bash
pytest tests/test_health.py -v
```
