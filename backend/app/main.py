from contextlib import asynccontextmanager
import asyncio
import logging
import sys

# ---------------------------------------------------------------------------
# Windows + psycopg async compatibility
# ---------------------------------------------------------------------------
# psycopg (v3) can have issues with Windows' default ProactorEventLoop.
# Use SelectorEventLoop for reliable async PostgreSQL operations.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    logger.info("VidyaRoom starting up")

    logger.info(
        "Config loaded: service=vidyaroom, whisper_model=%s, "
        "target_language=%s",
        settings.WHISPER_MODEL,
        settings.TARGET_LANGUAGE,
    )

    # -----------------------------------------------------------------------
    # FFmpeg
    # -----------------------------------------------------------------------
    # FFmpeg is required for audio preprocessing.
    from app.services.audio_preprocessor import (
        check_ffmpeg,
        FFmpegNotFoundError,
    )

    try:
        ffmpeg_path = check_ffmpeg()
        logger.info(
            "FFmpeg available at: %s",
            ffmpeg_path,
        )
    except FFmpegNotFoundError as exc:
        logger.error(
            "STARTUP ERROR: %s",
            exc,
        )
        raise

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    # Database schema is managed exclusively by Alembic.
    #
    # Run from the backend directory:
    #
    #     alembic upgrade head
    #
    # Do NOT call Base.metadata.create_all() here.
    logger.info(
        "Schema migrations are managed by Alembic "
        "(run: alembic upgrade head)"
    )

    yield

    logger.info("VidyaRoom shutting down")


# ===========================================================================
# FastAPI application
# ===========================================================================

app = FastAPI(
    title="VidyaRoom API",
    version="0.1.0",
    lifespan=lifespan,
)


# ===========================================================================
# CORS
# ===========================================================================

settings = get_settings()

# Read CORS origins from configuration.
configured_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

# Always support both common Next.js development URLs.
#
# localhost:
#     http://localhost:3000
#
# 127.0.0.1:
#     http://127.0.0.1:3000
#
# dict.fromkeys() removes duplicates while preserving order.
cors_origins = list(
    dict.fromkeys(
        configured_origins
        + [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)

logger.info(
    "CORS allowed origins: %s",
    cors_origins,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# Routers
# ===========================================================================

try:
    from app.api.auth import router as auth_router
    from app.api.lectures import router as lectures_router
    from app.api.qa import router as qa_router
    from app.api.websocket import router as ws_router
    from app.api.chat import router as chat_router
    from app.api.feedback import router as feedback_router

    # Authentication
    app.include_router(
        auth_router,
        prefix="/api/auth",
        tags=["auth"],
    )

    # Lectures
    app.include_router(
        lectures_router,
        prefix="/lectures",
        tags=["lectures"],
    )

    # Student/Teacher chat
    app.include_router(
        chat_router,
        prefix="/lectures",
        tags=["chat"],
    )

    # Q&A
    app.include_router(
        qa_router,
        prefix="/qa",
        tags=["qa"],
    )

    # WebSocket
    app.include_router(
        ws_router,
        tags=["websocket"],
    )

    # Teacher feedback / analytics
    app.include_router(
        feedback_router,
        prefix="/api/feedback",
        tags=["feedback"],
    )

    logger.info("All API routers mounted successfully")

except Exception as exc:
    logger.exception(
        "Could not mount sub-routers: %s",
        exc,
    )


# ===========================================================================
# Health check
# ===========================================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "vidyaroom",
    }