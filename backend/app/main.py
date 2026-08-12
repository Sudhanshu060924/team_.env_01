from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("VidyaRoom starting up")
    logger.info(
        "Config loaded: service=vidyaroom, whisper_model=%s, target_language=%s",
        settings.WHISPER_MODEL,
        settings.TARGET_LANGUAGE,
    )

    # Verify FFmpeg is available (required for audio preprocessing)
    from app.services.audio_preprocessor import check_ffmpeg, FFmpegNotFoundError
    try:
        check_ffmpeg()
    except FFmpegNotFoundError as exc:
        logger.error("STARTUP ERROR: %s", exc)
        raise  # abort startup with a clear message

    # Create database tables on startup
    from app.database.database import create_tables
    await create_tables()
    logger.info("Database tables ready")

    yield
    logger.info("VidyaRoom shutting down")


app = FastAPI(
    title="VidyaRoom API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
try:
    from app.api.lectures import router as lectures_router
    from app.api.qa import router as qa_router
    from app.api.websocket import router as ws_router

    app.include_router(lectures_router, prefix="/lectures", tags=["lectures"])
    app.include_router(qa_router, prefix="/qa", tags=["qa"])
    app.include_router(ws_router, tags=["websocket"])
except Exception as exc:  # pragma: no cover
    logger.warning("Could not mount sub-routers: %s", exc)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "vidyaroom"}
