'use client'

import { forwardRef, useCallback, useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import type { PlaybackSegmentItem } from '@/types/feedback'

interface LectureVideoProps {
  src?: string
  lectureId?: string          // when provided, enables playback tracking
  onTimeUpdate?: (currentTime: number) => void
  onEnded?: () => void
}

// ---------------------------------------------------------------------------
// Playback tracker — batches events; does NOT fire on every timeupdate
// ---------------------------------------------------------------------------

interface TrackerState {
  playCount: number
  pauseCount: number
  rewindCount: number
  forwardCount: number
  replayCount: number
  seekCount: number
  watchSeconds: number
  completionPct: number
  segments: Map<string, PlaybackSegmentItem>
  lastTime: number
  duration: number
  watchedSeconds: number
}

function makeTracker(): TrackerState {
  return {
    playCount: 0, pauseCount: 0, rewindCount: 0, forwardCount: 0,
    replayCount: 0, seekCount: 0, watchSeconds: 0, completionPct: 0,
    segments: new Map(), lastTime: 0, duration: 0, watchedSeconds: 0,
  }
}

const BUCKET = 30
const FLUSH_INTERVAL_MS = 60_000

function addSegment(tracker: TrackerState, time: number, eventType: string): void {
  const bucketStart = Math.floor(time / BUCKET) * BUCKET
  const key = `${bucketStart}-${eventType}`
  const existing = tracker.segments.get(key)
  if (existing) {
    existing.count += 1
  } else {
    tracker.segments.set(key, { start: bucketStart, end: bucketStart + BUCKET, event_type: eventType, count: 1 })
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const LectureVideo = forwardRef<HTMLVideoElement | null, LectureVideoProps>(
  function LectureVideo({ src, lectureId, onTimeUpdate, onEnded }, ref) {
    const trackerRef = useRef<TrackerState>(makeTracker())
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const isPlayingRef = useRef(false)
    const hasEndedRef = useRef(false)

    useEffect(() => {
      trackerRef.current = makeTracker()
      hasEndedRef.current = false
    }, [src, lectureId])

    const flush = useCallback(async (isFinal = false) => {
      if (!lectureId) return
      const t = trackerRef.current
      if (t.playCount === 0 && t.pauseCount === 0 && t.watchSeconds === 0 && !isFinal) return

      const payload = {
        play_count: t.playCount,
        pause_count: t.pauseCount,
        rewind_count: t.rewindCount,
        forward_count: t.forwardCount,
        replay_count: t.replayCount,
        seek_count: t.seekCount,
        watch_seconds: Math.round(t.watchSeconds),
        completion_pct: t.completionPct,
        revisit_segments: Array.from(t.segments.values()),
      }

      trackerRef.current = {
        ...makeTracker(),
        lastTime: t.lastTime,
        duration: t.duration,
        completionPct: t.completionPct,
        watchedSeconds: t.watchedSeconds,
        segments: new Map(),
      }

      try { await api.flushPlayback(lectureId, payload) } catch { /* fire-and-forget */ }
    }, [lectureId])

    useEffect(() => {
      if (!lectureId) return
      intervalRef.current = setInterval(() => { if (isPlayingRef.current) flush() }, FLUSH_INTERVAL_MS)
      return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
    }, [lectureId, flush])

    useEffect(() => {
      if (!lectureId) return
      const handleUnload = () => flush(true)
      window.addEventListener('beforeunload', handleUnload)
      return () => window.removeEventListener('beforeunload', handleUnload)
    }, [lectureId, flush])

    const handlePlay = useCallback(() => {
      isPlayingRef.current = true
      if (hasEndedRef.current) {
        trackerRef.current.replayCount += 1
        hasEndedRef.current = false
      } else {
        trackerRef.current.playCount += 1
      }
    }, [])

    const handlePause = useCallback(() => {
      isPlayingRef.current = false
      trackerRef.current.pauseCount += 1
      addSegment(trackerRef.current, trackerRef.current.lastTime, 'pause')
      flush()
    }, [flush])

    const handleEnded = useCallback(() => {
      isPlayingRef.current = false
      hasEndedRef.current = true
      trackerRef.current.completionPct = 100
      flush(true)
      onEnded?.()
    }, [flush, onEnded])

    const handleTimeUpdate = useCallback(
      (e: { currentTarget: HTMLVideoElement }) => {
        const video = e.currentTarget
        const current = video.currentTime
        const duration = video.duration || 0
        const t = trackerRef.current
        const delta = current - t.lastTime

        if (delta > 0 && delta < 5) {
          t.watchSeconds += delta
          t.watchedSeconds += delta
        } else if (delta < -2) {
          t.rewindCount += 1
          t.seekCount += 1
          addSegment(t, t.lastTime, 'rewind')
        } else if (delta > 5) {
          t.forwardCount += 1
          t.seekCount += 1
          addSegment(t, t.lastTime, 'forward')
        }

        t.lastTime = current
        t.duration = duration
        if (duration > 0) t.completionPct = Math.min(100, Math.round((current / duration) * 100))
        onTimeUpdate?.(current)
      },
      [onTimeUpdate],
    )

    const handleSeeked = useCallback(
      (e: { currentTarget: HTMLVideoElement }) => {
        const video = e.currentTarget
        const t = trackerRef.current
        const delta = video.currentTime - t.lastTime
        if (delta < -2) {
          addSegment(t, video.currentTime, 'replay')
          t.replayCount += 1
        }
      },
      [],
    )

    return (
      <div className="relative w-full bg-black overflow-hidden flex items-center justify-center border border-neutral-800 aspect-video lg:aspect-auto lg:h-full">
        {src ? (
          <video
            ref={ref}
            className="w-full h-full object-contain"
            src={src}
            controls
            onPlay={handlePlay}
            onPause={handlePause}
            onEnded={handleEnded}
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleSeeked}
            aria-label="Lecture video"
          />
        ) : (
          <div className="text-center text-neutral-600 select-none">
            <div className="text-5xl mb-3 opacity-30" aria-hidden="true">▶</div>
            <p className="text-sm text-neutral-500">No video loaded</p>
          </div>
        )}
      </div>
    )
  }
)

export default LectureVideo
