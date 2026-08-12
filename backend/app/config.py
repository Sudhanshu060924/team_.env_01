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

    # Localisation
    TARGET_LANGUAGE: str = "hi"

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
