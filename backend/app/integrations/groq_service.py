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


@lru_cache(maxsize=None)
def _make_client(api_key: str) -> AsyncGroq:
    """Create an AsyncGroq instance keyed by api_key (cached per unique key)."""
    return AsyncGroq(api_key=api_key)


def get_groq_client() -> AsyncGroq:
    """Return the AsyncGroq singleton for the current GROQ_API_KEY setting."""
    return _make_client(get_settings().GROQ_API_KEY)
