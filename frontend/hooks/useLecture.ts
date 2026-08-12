'use client'

import { useState, useCallback } from 'react'
import { Lecture, LectureStatus } from '@/types/lecture'
import { api } from '@/lib/api'

export function useLecture() {
  const [lecture, setLecture] = useState<Lecture | null>(null)
  const [status, setStatus] = useState<LectureStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const startLecture = useCallback(async (title: string, videoName: string) => {
    setStatus('starting')
    setError(null)
    try {
      const result = await api.startLecture({ title, video_name: videoName })
      setLecture(result)
      setStatus('live')
      return result
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start lecture'
      setError(msg)
      setStatus('error')
      return null
    }
  }, [])

  const completeLecture = useCallback(async () => {
    if (!lecture) return
    try {
      const result = await api.completeLecture(lecture.lecture_id)
      setLecture(result)
      setStatus('completed')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to complete lecture'
      setError(msg)
    }
  }, [lecture])

  const reset = useCallback(() => {
    setLecture(null)
    setStatus('idle')
    setError(null)
  }, [])

  return { lecture, status, error, startLecture, completeLecture, reset }
}
