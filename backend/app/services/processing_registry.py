"""
Processing Registry — tracks per-lecture background asyncio.Task objects.

Ensures at most one processing pipeline runs per lecture_id at any time.
Tasks are removed from the registry when they finish (success or failure).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProcessingRegistry:
    """
    In-process registry: lecture_id -> asyncio.Task

    Thread-safe enough for single-threaded asyncio event loop.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}

    def is_active(self, lecture_id: str) -> bool:
        """Return True if a non-done task exists for this lecture."""
        task = self._tasks.get(lecture_id)
        return task is not None and not task.done()

    def register(self, lecture_id: str, task: asyncio.Task) -> None:
        """Store the task. Attach a callback to auto-remove it when done."""
        self._tasks[lecture_id] = task

        def _on_done(t: asyncio.Task) -> None:
            self._tasks.pop(lecture_id, None)
            exc = t.exception() if not t.cancelled() else None
            if exc:
                logger.error(
                    "Processing task failed lecture_id=%s: %s",
                    lecture_id,
                    exc,
                    exc_info=exc,
                )
            else:
                logger.info("Processing task finished lecture_id=%s", lecture_id)

        task.add_done_callback(_on_done)

    def get(self, lecture_id: str) -> Optional[asyncio.Task]:
        return self._tasks.get(lecture_id)


# Module-level singleton
processing_registry = ProcessingRegistry()
