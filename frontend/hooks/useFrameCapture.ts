'use client'

/**
 * useFrameCapture
 *
 * Samples frames from a <video> element at a configurable interval while the
 * video is playing. Each frame is drawn onto a hidden canvas, encoded as a
 * JPEG (for efficiency), base64-encoded, and sent to the backend as a
 * `frame` WebSocket message.
 *
 * Message schema (matches backend _handle_frame):
 *   { type: "frame", lecture_id: "...", timestamp: <video.currentTime>, data: "<base64>" }
 *
 * Capture stops automatically when:
 *   - the video is paused / ended
 *   - `enabled` becomes false
 *   - the component unmounts
 */

import { useEffect, useRef } from 'react'

/** Max dimension (width or height) to which frames are downscaled before encoding. */
const MAX_DIMENSION = 640

interface UseFrameCaptureOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>
  lectureId: string | null
  sendMessage: (msg: object) => void
  enabled: boolean
  /** Milliseconds between frame samples (default: 3000 = 3 s) */
  intervalMs?: number
  /** JPEG quality 0–1 (default: 0.7) */
  jpegQuality?: number
}

export function useFrameCapture({
  videoRef,
  lectureId,
  sendMessage,
  enabled,
  intervalMs = 3000,
  jpegQuality = 0.7,
}: UseFrameCaptureOptions) {
  const intervalRef    = useRef<ReturnType<typeof setInterval> | null>(null)
  const canvasRef      = useRef<HTMLCanvasElement | null>(null)
  const lectureIdRef   = useRef(lectureId)
  const sendRef        = useRef(sendMessage)
  const jpegQualityRef = useRef(jpegQuality)

  // Keep refs in sync with props without re-triggering the effect
  lectureIdRef.current   = lectureId
  sendRef.current        = sendMessage
  jpegQualityRef.current = jpegQuality

  useEffect(() => {
    if (!enabled || !lectureId) {
      stopCapture()
      return
    }

    const video = videoRef.current
    if (!video) return

    // Lazily create a single off-screen canvas (never mounted to the DOM)
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
    }

    const capture = () => {
      const v = videoRef.current
      if (!v || v.paused || v.ended || v.readyState < 2) return

      const canvas = canvasRef.current!
      const ctx    = canvas.getContext('2d')
      if (!ctx) return

      // Downscale to stay within MAX_DIMENSION on the longer side
      const scale = Math.min(1, MAX_DIMENSION / Math.max(v.videoWidth, v.videoHeight, 1))
      const w     = Math.round(v.videoWidth  * scale)
      const h     = Math.round(v.videoHeight * scale)
      if (w === 0 || h === 0) return

      canvas.width  = w
      canvas.height = h

      try {
        ctx.drawImage(v, 0, 0, w, h)
      } catch {
        // drawImage can throw if the video has no displayable frame yet
        return
      }

      const dataUrl = canvas.toDataURL('image/jpeg', jpegQualityRef.current)
      // Strip the "data:image/jpeg;base64," prefix
      const base64  = dataUrl.split(',')[1]
      if (!base64) return

      sendRef.current({
        type:       'frame',
        lecture_id:  lectureIdRef.current,
        timestamp:   v.currentTime,
        data:        base64,
      })
    }

    // Start the periodic sampler
    intervalRef.current = setInterval(capture, intervalMs)

    return () => {
      stopCapture()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, lectureId])

  function stopCapture() {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }
}
