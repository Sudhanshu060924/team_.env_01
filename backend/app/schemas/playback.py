"""Pydantic schemas for Playback Analytics."""
from typing import List, Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Input from the frontend (student video player → batch flush)
# ---------------------------------------------------------------------------

class PlaybackSegmentItem(BaseModel):
    """One revisit/interaction segment within the video timeline."""
    start: float        # seconds
    end: float          # seconds
    event_type: str     # "pause" | "rewind" | "replay" | "seek" | "forward"
    count: int          # how many times this segment was affected


class PlaybackFlush(BaseModel):
    """
    A batched flush from the student video player.
    All counter values are DELTA values for this session.
    """
    play_count:    int   = 0
    pause_count:   int   = 0
    rewind_count:  int   = 0
    forward_count: int   = 0
    replay_count:  int   = 0
    seek_count:    int   = 0
    watch_seconds: float = 0.0       # total seconds watched in this session
    completion_pct: float = 0.0      # 0–100

    revisit_segments: List[PlaybackSegmentItem] = []

    @field_validator("completion_pct")
    @classmethod
    def clamp_completion(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


# ---------------------------------------------------------------------------
# Output — aggregated teacher-facing stats
# ---------------------------------------------------------------------------

class RevisitSegment(BaseModel):
    """One notable timeline segment for the teacher."""
    start: float
    end: float
    event_type: str
    count: int
    label: str   # "Frequently revisited section" | "Potentially difficult section" | etc.


class LectureEngagementStats(BaseModel):
    """Aggregated playback engagement for a lecture or set of lectures."""
    total_views:        int   = 0
    avg_watch_seconds:  float = 0.0
    avg_completion_pct: float = 0.0
    play_count:         int   = 0
    pause_count:        int   = 0
    rewind_count:       int   = 0
    forward_count:      int   = 0
    replay_count:       int   = 0
    seek_count:         int   = 0
    revisit_segments:   List[RevisitSegment] = []
