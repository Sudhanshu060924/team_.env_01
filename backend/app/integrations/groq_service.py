"""
Groq API client — shared singleton for the whole application.

Usage:
    from app.integrations.groq_service import get_groq_client
    client = get_groq_client()
    # client is an AsyncGroq instance
"""
from functools import lru_cache

from groq import AsyncGroq

from app.config import get_settings


@lru_cache(maxsize=1)
def get_groq_client() -> AsyncGroq:
    """Return the module-level AsyncGroq singleton (created once per process)."""
    settings = get_settings()
    return AsyncGroq(api_key=settings.GROQ_API_KEY)
