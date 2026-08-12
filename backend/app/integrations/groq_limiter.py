"""
Groq rate-limit helpers.

Provides:
  - A process-wide asyncio semaphore that caps simultaneous Groq calls
    (MAX_CONCURRENT_GROQ_REQUESTS).
  - groq_chat_with_retry(): wraps client.chat.completions.create with
    exponential backoff on HTTP 429 (groq.RateLimitError).

Usage
-----
    from app.integrations.groq_limiter import groq_chat_with_retry

    response = await groq_chat_with_retry(
        client=client,
        model=settings.GROQ_MODEL,
        messages=[...],
        temperature=0.2,
        max_tokens=512,
    )
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazily-created semaphore — built on first use so the event loop is running.
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        limit = get_settings().MAX_CONCURRENT_GROQ_REQUESTS
        _semaphore = asyncio.Semaphore(limit)
        logger.debug("groq_limiter: semaphore initialised max=%d", limit)
    return _semaphore


def reset_semaphore() -> None:
    """Reset the module-level semaphore (used in tests only)."""
    global _semaphore
    _semaphore = None


async def groq_chat_with_retry(client: Any, **kwargs: Any) -> Any:
    """
    Call client.chat.completions.create(**kwargs) with:
      - Concurrency limited via semaphore (MAX_CONCURRENT_GROQ_REQUESTS).
      - Exponential backoff on groq.RateLimitError (HTTP 429).
        Retries: GROQ_MAX_RETRIES times, waits 1s then 2s.

    Raises the last exception if all retries are exhausted.
    """
    settings = get_settings()
    max_retries = settings.GROQ_MAX_RETRIES

    # Import lazily to avoid hard dependency when key is absent.
    try:
        from groq import RateLimitError
    except ImportError:  # pragma: no cover
        RateLimitError = Exception  # type: ignore[misc,assignment]

    sem = _get_semaphore()
    last_exc: Exception | None = None

    async with sem:
        for attempt in range(max_retries + 1):
            try:
                logger.debug("groq_limiter: calling Groq (attempt %d)", attempt + 1)
                return await client.chat.completions.create(**kwargs)
            except RateLimitError as exc:
                last_exc = exc
                if attempt >= max_retries:
                    logger.warning(
                        "groq_limiter: rate-limited; max retries (%d) exhausted",
                        max_retries,
                    )
                    raise
                wait = 2 ** attempt  # 1 s, 2 s
                logger.warning(
                    "groq_limiter: Groq rate limited (429); retrying in %ds (attempt %d/%d)",
                    wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)

    # Unreachable — satisfy type checkers.
    raise RuntimeError("groq_chat_with_retry: unexpected exit")  # pragma: no cover
