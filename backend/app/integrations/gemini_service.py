"""
Gemini API client — used exclusively for lecture translation.

The google-genai SDK is used directly (no LangChain wrapper).
The client is constructed on first call and cached for the process lifetime.

Usage:
    from app.integrations.gemini_service import gemini_translate

    translated = await gemini_translate(
        system_prompt="...",
        user_prompt="...",
        model="gemini-2.5-flash-lite",
    )
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client():
    """Return a cached google.genai.Client instance."""
    from google import genai  # type: ignore[import]

    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def gemini_translate(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.2,
    max_output_tokens: int = 512,
) -> str:
    """
    Call the Gemini API and return the response text.

    Uses google.genai.Client.aio.models.generate_content (async).
    Raises on API error — caller is responsible for exception handling.
    """
    from google.genai import types  # type: ignore[import]

    client = _get_client()
    logger.debug("gemini_service: calling model=%s", model)

    response = await client.aio.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    return response.text or ""
