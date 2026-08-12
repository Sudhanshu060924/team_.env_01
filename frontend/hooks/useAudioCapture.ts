'use client'

/**
 * useAudioCapture
 *
 * Taps into a <video> element's audio track using the Web Audio API +
 * MediaRecorder. Every `chunkMs` milliseconds the recorder is stopped,
 * a complete decodable blob is emitted via ondataavailable, base64-encoded,
 * and sent to the backend as an `audio_chunk` WS message. Then a fresh
 * recorder is immediately started for the next chunk.
 *
 * Why stop+restart instead of start(timeslice)?
 *   `start(timeslice)` fires ondataavailable with partial, non-decodable
 *   header-less blobs after the first chunk. Groq Whisper needs a full,
 *   self-contained audio file each time. stop() guarantees that.
 */

import { useEffect, useRef } from 'react'

interface UseAudioCaptureOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>
  lectureId: string | null
  sendMessage: (msg: object) => void
  enabled: boolean
  /** Milliseconds of audio per chunk sent to Whisper (default: 5000) */
  chunkMs?: number
}

export function useAudioCapture({
  videoRef,
  lectureId,
  sendMessage,
  enabled,
  chunkMs = 5000,
}: UseAudioCaptureOptions) {
  // Keep mutable refs so the interval callback always sees current values
  const ctxRef        = useRef<AudioContext | null>(null)
  const destRef       = useRef<MediaStreamAudioDestinationNode | null>(null)
  const recorderRef   = useRef<MediaRecorder | null>(null)
  const intervalRef   = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeRef     = useRef(false)   // prevents re-entrant startChunk calls
  const mimeTypeRef   = useRef('audio/webm;codecs=opus')
  const lectureIdRef  = useRef(lectureId)
  const sendRef       = useRef(sendMessage)

  // Keep refs in sync with props without restarting the effect
  lectureIdRef.current = lectureId
  sendRef.current      = sendMessage

  useEffect(() => {
    if (!enabled || !lectureId) {
      teardown()
      return
    }

    const video = videoRef.current
    if (!video) return

    const init = () => {
      if (activeRef.current) return
      activeRef.current = true

      try {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof window.AudioContext })
            .webkitAudioContext
        const ctx = new AudioCtx()
        ctxRef.current = ctx

        const source = ctx.createMediaElementSource(video)
        const dest   = ctx.createMediaStreamDestination()
        destRef.current = dest

        source.connect(dest)
        source.connect(ctx.destination) // keep sound playing through speakers

        // Determine best mime type once
        mimeTypeRef.current = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/ogg;codecs=opus'

        // Start the first recording window
        startChunk()

        // Every chunkMs: stop current recorder (fires ondataavailable with a
        // complete blob) then immediately start the next window
        intervalRef.current = setInterval(() => {
          cycleChunk()
        }, chunkMs)
      } catch (err) {
        console.warn('[useAudioCapture] init failed:', err)
        activeRef.current = false
      }
    }

    if (video.readyState >= 1) {
      init()
    } else {
      video.addEventListener('loadedmetadata', init, { once: true })
    }

    return () => {
      teardown()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, lectureId])

  // ── helpers ──────────────────────────────────────────────────────────

  function startChunk() {
    const dest = destRef.current
    if (!dest) return

    const recorder = new MediaRecorder(dest.stream, {
      mimeType: mimeTypeRef.current,
    })
    recorderRef.current = recorder

    recorder.ondataavailable = async (e) => {
      if (!e.data || e.data.size < 500) return // skip silent / empty blobs

      const video     = videoRef.current
      const timestamp = video ? video.currentTime : 0

      try {
        const buffer = await e.data.arrayBuffer()
        // Use Uint8Array + reduce for large buffers (avoids stack overflow)
        const b64 = btoa(
          new Uint8Array(buffer).reduce(
            (s, b) => s + String.fromCharCode(b),
            ''
          )
        )

        sendRef.current({
          type:       'audio_chunk',
          lecture_id: lectureIdRef.current,
          timestamp,
          filename:   'audio.webm',
          data:       b64,
        })
      } catch (err) {
        console.warn('[useAudioCapture] chunk encode error:', err)
      }
    }

    recorder.start() // no timeslice — full blob on stop()
  }

  function cycleChunk() {
    const recorder = recorderRef.current
    if (!recorder || recorder.state === 'inactive') {
      // recorder was stopped externally; just start a fresh one
      startChunk()
      return
    }
    // stop() triggers ondataavailable → then we start the next window
    recorder.onstop = () => {
      startChunk()
    }
    recorder.stop()
  }

  function teardown() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    try { recorderRef.current?.stop() } catch { /* ignore */ }
    recorderRef.current = null
    destRef.current?.stream.getTracks().forEach((t) => t.stop())
    destRef.current = null
    ctxRef.current?.close()
    ctxRef.current = null
    activeRef.current = false
  }
}
