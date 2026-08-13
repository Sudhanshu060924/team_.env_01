'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'
import Button from '@/components/ui/Button'

const ACCEPTED_TYPES = '.mp4,.mov,.webm,.mkv,.avi'
const MAX_SIZE_MB = 500

type UploadState = 'idle' | 'uploading' | 'success' | 'error'

export default function TeacherUploadPage() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [uploadedLectureId, setUploadedLectureId] = useState<string | null>(null)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
    if (!isLoading && isAuthenticated && user?.role !== 'teacher') {
      router.replace('/student/dashboard')
    }
  }, [isLoading, isAuthenticated, user, router])

  if (!user) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setErrorMsg(`File too large. Maximum size is ${MAX_SIZE_MB} MB.`)
      return
    }

    setErrorMsg(null)
    setVideoFile(file)

    // Auto-fill title from filename if title is still empty
    if (!title.trim()) {
      const name = file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ')
      setTitle(name)
    }
  }

  const handleUpload = async () => {
    if (!videoFile || !title.trim()) return

    setUploadState('uploading')
    setErrorMsg(null)

    try {
      // Step 1 — create the lecture record (teacher_id set from auth cookie)
      const lecture = await api.startLecture({ title: title.trim() })

      // Step 2 — upload the video to Cloudinary via the backend
      const updated = await api.uploadLectureVideo(lecture.lecture_id, videoFile)

      setUploadedLectureId(updated.lecture_id)
      setUploadState('success')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed. Please try again.')
      setUploadState('error')
    }
  }

  const handleReset = () => {
    setTitle('')
    setVideoFile(null)
    setUploadState('idle')
    setErrorMsg(null)
    setUploadedLectureId(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <AppShell role="teacher">
      <AppHeader
        title="Upload Video"
        subtitle="Upload a lecture recording for your students"
      />

      <PageContainer maxWidth="sm">
        {uploadState === 'success' ? (
          /* ── Success state ────────────────────────────────────────────── */
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-green-50 border border-green-200 flex items-center justify-center text-green-600 text-xl">
              ✓
            </div>
            <div>
              <p className="font-semibold text-black">Upload successful!</p>
              <p className="text-sm text-gray-500 mt-1">
                Your lecture is now available to students.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 mt-2">
              <Button variant="primary" onClick={() => router.push('/teacher/dashboard')}>
                Back to Dashboard
              </Button>
              <Button variant="secondary" onClick={handleReset}>
                Upload Another
              </Button>
            </div>
          </div>
        ) : (
          /* ── Upload form ──────────────────────────────────────────────── */
          <div className="bg-white border border-gray-200 rounded-lg p-6 flex flex-col gap-6">

            {/* Lecture title */}
            <div className="flex flex-col gap-2">
              <label
                htmlFor="upload-title"
                className="text-[11px] font-semibold uppercase tracking-widest text-gray-600"
              >
                Lecture Title <span className="text-red-500">*</span>
              </label>
              <input
                id="upload-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Introduction to Binary Search"
                disabled={uploadState === 'uploading'}
                className="bg-white text-black border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 transition-colors disabled:opacity-50"
              />
            </div>

            {/* Video file picker */}
            <div className="flex flex-col gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-gray-600">
                Video File <span className="text-red-500">*</span>
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadState === 'uploading'}
                className="cursor-pointer border border-dashed border-gray-300 hover:border-yellow-500 px-4 py-8 flex flex-col items-center gap-2 transition-colors w-full text-center bg-white hover:bg-yellow-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {videoFile ? (
                  <>
                    <svg className="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.862v6.276a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <span className="text-sm text-black font-medium break-all">{videoFile.name}</span>
                    <span className="text-xs text-gray-500">
                      {(videoFile.size / 1024 / 1024).toFixed(1)} MB · click to change
                    </span>
                  </>
                ) : (
                  <>
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    <span className="text-sm text-gray-700">Click to choose a video file</span>
                    <span className="text-xs text-gray-500">MP4, MOV, WebM, MKV, AVI · max {MAX_SIZE_MB} MB</span>
                  </>
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_TYPES}
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            {/* Error message */}
            {errorMsg && (
              <p className="text-xs text-red-700 border border-red-200 px-3 py-2 bg-red-50 rounded">
                ⚠ {errorMsg}
              </p>
            )}

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                variant="primary"
                onClick={handleUpload}
                loading={uploadState === 'uploading'}
                disabled={uploadState === 'uploading' || !videoFile || !title.trim()}
              >
                {uploadState === 'uploading' ? 'Uploading…' : 'Upload Video'}
              </Button>
              <Link href="/teacher/dashboard">
                <Button variant="secondary" disabled={uploadState === 'uploading'}>
                  Cancel
                </Button>
              </Link>
            </div>

            {uploadState === 'uploading' && (
              <p className="text-xs text-gray-500 text-center">
                Uploading to Cloudinary, please wait…
              </p>
            )}
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}
