"""
Playback Analytics service.

Stores and aggregates batched video-player events per student per lecture.
Completely separate from:
  - chat_service   (Student ↔ Teacher doubts)
  - chatbot_service (Student ↔ AI chatbot)
  - rating_service  (Lecture ratings)

The frontend batches/debounces events and POSTs a single payload per flush.
One row is upserted per (lecture_id, student_id) — counters are incremented
and revisit segments are merged on each flush.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PlaybackAnalytics
from app.schemas.playback import (
    PlaybackFlush,
    PlaybackSegmentItem,
    LectureEngagementStats,
    RevisitSegment,
)


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------

async def flush_playback(
    db: AsyncSession,
    lecture_id: str,
    student_id: str,
    payload: PlaybackFlush,
) -> None:
    """
    Upsert the playback row for (student, lecture), incrementing all counters
    and merging revisit segment heat data.
    """
    result = await db.execute(
        select(PlaybackAnalytics).where(
            PlaybackAnalytics.lecture_id == lecture_id,
            PlaybackAnalytics.student_id == student_id,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = PlaybackAnalytics(
            lecture_id=lecture_id,
            student_id=student_id,
            play_count=payload.play_count,
            pause_count=payload.pause_count,
            rewind_count=payload.rewind_count,
            forward_count=payload.forward_count,
            replay_count=payload.replay_count,
            seek_count=payload.seek_count,
            total_watch_seconds=payload.watch_seconds,
            completion_pct=payload.completion_pct,
            revisit_segments=_merge_segments([], payload.revisit_segments),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(row)
    else:
        row.play_count    += payload.play_count
        row.pause_count   += payload.pause_count
        row.rewind_count  += payload.rewind_count
        row.forward_count += payload.forward_count
        row.replay_count  += payload.replay_count
        row.seek_count    += payload.seek_count
        # Watch seconds: keep the maximum observed so far (avoids double-counting
        # when the user watches the same segment multiple times).
        if payload.watch_seconds > row.total_watch_seconds:
            row.total_watch_seconds = payload.watch_seconds
        # Completion: keep maximum
        if payload.completion_pct > row.completion_pct:
            row.completion_pct = payload.completion_pct
        row.revisit_segments = _merge_segments(
            list(row.revisit_segments or []), payload.revisit_segments
        )
        row.updated_at = datetime.now(timezone.utc)

    await db.commit()


def _merge_segments(
    existing: List[Dict[str, Any]],
    incoming: List[PlaybackSegmentItem],
) -> List[Dict[str, Any]]:
    """
    Merge incoming revisit segments into the stored list.
    Segments that overlap the same 30-second bucket and share an event_type
    are merged by incrementing counts; new segments are appended.
    Uses 30-second buckets for grouping (start snapped to nearest 30s).
    """
    BUCKET = 30  # seconds

    # Build index: (bucket_start, event_type) -> index in existing
    index: Dict[tuple, int] = {}
    for i, seg in enumerate(existing):
        bucket = int(seg.get("start", 0) // BUCKET) * BUCKET
        key = (bucket, seg.get("event_type", ""))
        index[key] = i

    for item in incoming:
        bucket = int(item.start // BUCKET) * BUCKET
        key = (bucket, item.event_type)
        if key in index:
            existing[index[key]]["count"] = (
                existing[index[key]].get("count", 0) + item.count
            )
        else:
            new_seg: Dict[str, Any] = {
                "start": float(bucket),
                "end": float(bucket + BUCKET),
                "event_type": item.event_type,
                "count": item.count,
            }
            index[key] = len(existing)
            existing.append(new_seg)

    return existing


# ---------------------------------------------------------------------------
# Aggregated engagement stats (teacher-facing)
# ---------------------------------------------------------------------------

async def get_lecture_engagement(
    db: AsyncSession,
    lecture_ids: List[str],
) -> LectureEngagementStats:
    """
    Return aggregated playback stats across all students for the given
    lecture_ids.  Returns a zero-state when there are no rows.
    """
    if not lecture_ids:
        return LectureEngagementStats()

    stmt = select(
        func.count(PlaybackAnalytics.id).label("viewer_count"),
        func.sum(PlaybackAnalytics.play_count).label("play_count"),
        func.sum(PlaybackAnalytics.pause_count).label("pause_count"),
        func.sum(PlaybackAnalytics.rewind_count).label("rewind_count"),
        func.sum(PlaybackAnalytics.forward_count).label("forward_count"),
        func.sum(PlaybackAnalytics.replay_count).label("replay_count"),
        func.sum(PlaybackAnalytics.seek_count).label("seek_count"),
        func.avg(PlaybackAnalytics.total_watch_seconds).label("avg_watch_seconds"),
        func.avg(PlaybackAnalytics.completion_pct).label("avg_completion_pct"),
    ).where(PlaybackAnalytics.lecture_id.in_(lecture_ids))

    result = await db.execute(stmt)
    row = result.first()

    if not row or (row.viewer_count or 0) == 0:
        return LectureEngagementStats()

    # Collect all revisit_segment lists across matching rows
    seg_rows = await db.execute(
        select(PlaybackAnalytics.revisit_segments).where(
            PlaybackAnalytics.lecture_id.in_(lecture_ids)
        )
    )
    all_segs: List[PlaybackSegmentItem] = []
    for (segs,) in seg_rows.all():
        for s in (segs or []):
            try:
                all_segs.append(PlaybackSegmentItem(
                    start=float(s.get("start", 0)),
                    end=float(s.get("end", 0)),
                    event_type=str(s.get("event_type", "")),
                    count=int(s.get("count", 0)),
                ))
            except Exception:
                pass

    merged = _merge_segments([], all_segs)

    # Flag high-activity segments
    revisit_segments: List[RevisitSegment] = []
    for seg in sorted(merged, key=lambda s: s.get("count", 0), reverse=True)[:20]:
        count = seg.get("count", 0)
        if count < 5:
            continue
        event_type = seg.get("event_type", "")
        if event_type in ("replay", "rewind") and count >= 15:
            label = "Frequently revisited section"
        elif event_type in ("replay", "rewind", "pause") and count >= 8:
            label = "Potentially difficult section"
        else:
            label = "Active engagement section"

        revisit_segments.append(RevisitSegment(
            start=seg.get("start", 0),
            end=seg.get("end", 0),
            event_type=event_type,
            count=count,
            label=label,
        ))

    return LectureEngagementStats(
        total_views=int(row.viewer_count or 0),
        avg_watch_seconds=round(float(row.avg_watch_seconds or 0), 1),
        avg_completion_pct=round(float(row.avg_completion_pct or 0), 1),
        play_count=int(row.play_count or 0),
        pause_count=int(row.pause_count or 0),
        rewind_count=int(row.rewind_count or 0),
        forward_count=int(row.forward_count or 0),
        replay_count=int(row.replay_count or 0),
        seek_count=int(row.seek_count or 0),
        revisit_segments=revisit_segments,
    )
