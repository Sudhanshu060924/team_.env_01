from contextlib import asynccontextmanager
import asyncio
import logging
import sys

# psycopg (v3) does not support Windows' default ProactorEventLoop.
# Force SelectorEventLoop before uvicorn starts so all async DB calls work.
# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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

    # ── Database ───────────────────────────────────────────────────────────
    # Schema migrations are now managed by Alembic.
    # Run:  alembic upgrade head   (from backend/)  before starting the server.
    #
    # create_tables() (Base.metadata.create_all) is intentionally NOT called
    # here so that Alembic — not SQLAlchemy metadata — owns the Neon schema.
    #
    # If you are starting a completely fresh development database with no
    # existing tables you can run:
    #   python -c "import asyncio; from app.database.database import create_tables; asyncio.run(create_tables())"
    # but that should never be done against the production Neon instance.
    logger.info("Schema migrations are managed by Alembic (run: alembic upgrade head)")

    yield
    logger.info("VidyaRoom shutting down")



app = FastAPI(
    title="VidyaRoom API",
    version="0.1.0",
    lifespan=lifespan,
)

# Build the allowed-origins list from settings.
# "allow_origins + allow_credentials=True" is illegal with a bare wildcard "*"
# (browsers reject it).  We always use explicit origins so credentials work.
_settings = get_settings()
_cors_origins = [o.strip() for o in _settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
try:
    from app.api.auth import router as auth_router
    from app.api.lectures import router as lectures_router
    from app.api.qa import router as qa_router
    from app.api.websocket import router as ws_router
    from app.api.chat import router as chat_router

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(lectures_router, prefix="/lectures", tags=["lectures"])
    app.include_router(chat_router, prefix="/lectures", tags=["chat"])
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
