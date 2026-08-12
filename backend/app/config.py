from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database (Phase 2+)
    DATABASE_URL: str = ""

    # Groq — LLM inference (Phase 7+)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-8b-8192"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
