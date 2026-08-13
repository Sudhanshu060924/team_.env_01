from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database (Phase 2+)
    DATABASE_URL: str = ""

    # Cloudinary — video storage
    CLOUD_NAME: str = ""
    CLOUD_API_KEY: str = ""
    CLOUD_API_SECRET: str = ""


    # Groq — LLM inference (Phase 7+)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Gemini — translation only (replaces Groq for translation)
    GEMINI_API_KEY: str = ""
    GEMINI_TRANSLATION_MODEL: str = "gemini-3.5-flash-lite"

    # Groq — Whisper speech-to-text (Phase 5)
    # Accepted values: "turbo"  → whisper-large-v3-turbo  (default, faster)
    #                  "large"  → whisper-large-v3         (most accurate)
    WHISPER_MODEL: str = "turbo"
    # ISO-639-1 language hint forwarded to Whisper (leave blank for auto-detect)
    WHISPER_LANGUAGE: str = ""

    # Localisation
    TARGET_LANGUAGE: str = "hi"

    # Audio preprocessing pipeline (Phase 5 — FFmpeg)
    AUDIO_SAMPLE_RATE: int = 16000   # Hz — target sample rate for Whisper
    AUDIO_CHANNELS: int = 1          # 1 = mono
    AUDIO_HIGHPASS: int = 100        # Hz — removes low-frequency rumble
    AUDIO_LOWPASS: int = 8000        # Hz — removes high-frequency hiss
    AUDIO_NOISE_REDUCTION: int = 12  # afftdn nr= value (0–97); keep moderate
    AUDIO_NOISE_FLOOR: int = -40     # afftdn nf= value (dBFS)

    # Set to true during local development to save cleaned audio chunks
    # to backend/debug_audio/ for inspection.
    SAVE_DEBUG_AUDIO: bool = False

    # Frontend URLs (optional, used in CORS / links)
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    NEXT_PUBLIC_WS_URL: str = "ws://localhost:8000"

    # Comma-separated list of allowed CORS origins.
    # Use "*" only for public APIs that never set credentials.
    # Default covers local dev (Next.js dev server).
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Groq rate-limit management ────────────────────────────────────────────
    # How often (seconds) topic detection may run at most.
    TOPIC_DETECTION_INTERVAL_SECONDS: int = 30
    # How often (seconds) important-event detection may run at most.
    IMPORTANT_EVENT_INTERVAL_SECONDS: int = 30
    # Hard character cap for each bounded context string sent to Groq.
    MAX_TRANSLATION_CONTEXT_CHARS: int = 4000
    MAX_TOPIC_CONTEXT_CHARS: int = 5000
    MAX_EVENT_CONTEXT_CHARS: int = 5000
    # Maximum simultaneous Groq requests (semaphore).
    MAX_CONCURRENT_GROQ_REQUESTS: int = 1
    # Maximum number of 429 retries per Groq call.
    GROQ_MAX_RETRIES: int = 2
    # Minimum transcript length (chars) to bother calling Groq.
    MIN_TRANSCRIPT_CHARS: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
