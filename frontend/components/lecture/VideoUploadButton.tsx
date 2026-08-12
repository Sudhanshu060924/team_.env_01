'use client'

import React, { useRef, useState } from 'react'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import Button from '@/components/ui/Button'

interface VideoUploadButtonProps {
  lecture: Lecture
  onUploaded?: (_updated: Lecture) => void
}

const ACCEPTED_TYPES = '.mp4,.mov,.webm,.mkv,.avi'
const MAX_SIZE_MB = 500

export default function VideoUploadButton({ lecture, onUploaded }: VideoUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploaded, setUploaded] = useState(!!lecture.video_url)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Client-side size check
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Maximum size is ${MAX_SIZE_MB} MB.`)
      return
    }

    setError(null)
    setUploading(true)
    try {
      const updated = await api.uploadLectureVideo(lecture.lecture_id, file)
      setUploaded(true)
      onUploaded?.(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to upload video. Please try again.')
    } finally {
      setUploading(false)
      // Reset input so the same file can be re-selected
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="hidden"
        onChange={handleFileChange}
        aria-label="Upload video file"
      />
      <Button
        variant={uploaded ? 'secondary' : 'primary'}
        size="sm"
        loading={uploading}
        disabled={uploading}
        onClick={() => {
          setError(null)
          inputRef.current?.click()
        }}
      >
        {uploading
          ? 'Uploading…'
          : uploaded
          ? '↑ Replace Video'
          : '↑ Upload Video'}
      </Button>
      {error && (
        <p className="text-xs text-red-600 max-w-[200px]">{error}</p>
      )}
      {uploaded && !uploading && !error && (
        <p className="text-xs text-green-600">Video uploaded ✓</p>
      )}
    </div>
  )
}
