'use client'

import { useRef, useState, useCallback, useId } from 'react'
import { useLecture } from '@/hooks/useLecture'
import { useLectureWebSocket } from '@/hooks/useLectureWebSocket'
import { useAudioCapture } from '@/hooks/useAudioCapture'
import LectureHeader from '@/components/LectureHeader'
import VideoPlayer from '@/components/VideoPlayer'
import LiveTranscription, { TranscriptLine } from '@/components/LiveTranscription'
import TopicPanel from '@/components/TopicPanel'
import ImportantEvents from '@/components/ImportantEvents'
import NotesPanel from '@/components/NotesPanel'
import ChatPanel from '@/components/ChatPanel'
import { WSMessage, TopicState, ImportantEvent, ChatMessage } from '@/types/ai'

export default function HomePage() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uid = useId()

  // ── Lecture session ────────────────────────────────────────────────
  const { lecture, status: lectureStatus, error, startLecture, completeLecture } = useLecture()
  const [lectureTitle, setLectureTitle] = useState('Demo Lecture')

  // ── Selected video file ────────────────────────────────────────────
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoSrc, setVideoSrc] = useState<string | null>(null)

  // ── AI state ───────────────────────────────────────────────────────
  const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[]>([])
  const [topic, setTopic] = useState<TopicState | null>(null)
  const [importantEvents, setImportantEvents] = useState<ImportantEvent[]>([])
  const [notes, setNotes] = useState<string | null>(null)
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])

  // ── Video file picker ──────────────────────────────────────────────
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setVideoFile(file)
    setVideoSrc((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
    const name = file.name.replace(/\.[^.]+$/, '')
    setLectureTitle(name || 'Demo Lecture')
  }, [])

  // ── WebSocket message router ───────────────────────────────────────
  const handleWsMessage = useCallback((msg: WSMessage) => {
    switch (msg.type) {
      // Live transcription from Groq Whisper (Phase 5)
      case 'speech_event':
        if (msg.content) {
          setTranscriptLines((prev) => [
            ...prev,
            {
              timestamp: msg.timestamp ?? 0,
              text: msg.content!,
              language: (msg.metadata as Record<string, string>)?.language ?? 'en',
            },
          ])
        }
        break

      case 'topic_update':
        if (msg.content) {
          setTopic({
            topic: msg.content,
            subtopic: (msg.metadata as Record<string, string>)?.subtopic ?? '',
            timestamp: msg.timestamp ?? 0,
          })
        }
        break

      case 'important_event':
      case 'board_event':
        if (msg.content) {
          setImportantEvents((prev) => [
            ...prev,
            {
              id: `${uid}-${Date.now()}`,
              timestamp: msg.timestamp ?? 0,
              content: msg.content!,
              isFormula: !!(msg.metadata as Record<string, boolean>)?.is_formula,
            },
          ])
        }
        break

      case 'notes':
        if (msg.content) {
          setNotes(msg.content)
          setIsGeneratingNotes(false)
        }
        break

      case 'lecture_completed':
        setIsGeneratingNotes(true)
        break

      case 'answer':
        if (msg.content) {
          setChatMessages((prev) => [
            ...prev,
            {
              id: `ai-${Date.now()}`,
              role: 'ai',
              content: msg.content!,
              timestamp: Date.now(),
            },
          ])
        }
        break

      default:
        break
    }
  }, [uid])

  const { status: wsStatus, sendMessage } = useLectureWebSocket({
    lectureId: lecture?.lecture_id ?? null,
    onMessage: handleWsMessage,
  })

  // ── Audio capture → Groq Whisper ───────────────────────────────────
  const isLive = lectureStatus === 'live'

  useAudioCapture({
    videoRef,
    lectureId: lecture?.lecture_id ?? null,
    sendMessage,
    enabled: isLive,
    chunkMs: 5000,
  })

  // ── Lecture start ──────────────────────────────────────────────────
  const handleStart = async () => {
    const fileName = videoFile?.name ?? 'demo.mp4'
    const result = await startLecture(lectureTitle, fileName)
    if (result) {
      videoRef.current?.play().catch(() => {})
    }
  }

  // ── Video ended ────────────────────────────────────────────────────
  const handleVideoEnded = useCallback(() => {
    if (!lecture) return
    sendMessage({
      type: 'lecture_completed',
      lecture_id: lecture.lecture_id,
      timestamp: videoRef.current?.duration ?? 0,
    })
    completeLecture()
  }, [lecture, sendMessage, completeLecture])

  // ── Chat ───────────────────────────────────────────────────────────
  const handleQuestion = useCallback((question: string) => {
    if (!lecture) return
    setChatMessages((prev) => [
      ...prev,
      {
        id: `student-${Date.now()}`,
        role: 'student',
        content: question,
        timestamp: Date.now(),
      },
    ])
    sendMessage({
      type: 'question',
      lecture_id: lecture.lecture_id,
      content: question,
      timestamp: videoRef.current?.currentTime ?? 0,
    })
  }, [lecture, sendMessage])

  const isCompleted = lectureStatus === 'completed'
  const canStart = lectureStatus === 'idle' || lectureStatus === 'error' || lectureStatus === 'starting'

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* ── Header ──────────────────────────────────────────────── */}
      <LectureHeader
        title={lecture?.title ?? 'VidyaRoom'}
        wsStatus={wsStatus}
        lectureStatus={lectureStatus}
      />

      {/* ── Start screen ────────────────────────────────────────── */}
      {canStart && (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-gray-900 rounded-xl p-8 w-full max-w-sm flex flex-col gap-5 shadow-lg">
            <h1 className="text-2xl font-bold text-white">Start Lecture</h1>

            {/* Video file picker */}
            <div className="flex flex-col gap-2">
              <label className="text-xs text-gray-400 uppercase tracking-wider">Video File</label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="cursor-pointer border-2 border-dashed border-gray-700 hover:border-indigo-500 rounded-lg px-4 py-5 flex flex-col items-center gap-2 transition-colors"
              >
                {videoFile ? (
                  <>
                    <span className="text-2xl">🎬</span>
                    <span className="text-sm text-gray-200 text-center break-all">{videoFile.name}</span>
                    <span className="text-xs text-gray-500">
                      {(videoFile.size / 1024 / 1024).toFixed(1)} MB · click to change
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-2xl opacity-40">▶</span>
                    <span className="text-sm text-gray-400">Click to choose a video file</span>
                    <span className="text-xs text-gray-600">MP4, WebM, MOV, MKV…</span>
                  </>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            {/* Lecture title */}
            <div className="flex flex-col gap-2">
              <label className="text-xs text-gray-400 uppercase tracking-wider">Lecture Title</label>
              <input
                type="text"
                value={lectureTitle}
                onChange={(e) => setLectureTitle(e.target.value)}
                className="bg-gray-800 text-gray-100 rounded px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="e.g. Binary Search"
              />
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <button
              onClick={handleStart}
              disabled={lectureStatus === 'starting' || !videoFile}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-colors"
            >
              {lectureStatus === 'starting' ? 'Starting…' : '▶  Start Lecture'}
            </button>

            {!videoFile && (
              <p className="text-xs text-gray-600 text-center">Select a video to enable start</p>
            )}
          </div>
        </div>
      )}

      {/* ── Live / Completed view ────────────────────────────────── */}
      {(isLive || isCompleted) && (
        <>
          <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 min-h-0">
            {/* Left column */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              <VideoPlayer
                ref={videoRef}
                src={videoSrc ?? undefined}
                onEnded={handleVideoEnded}
              />
              <LiveTranscription lines={transcriptLines} />
            </div>

            {/* Right column */}
            <div className="flex flex-col gap-4">
              <TopicPanel topic={topic} />
              <ImportantEvents events={importantEvents} />
            </div>
          </main>

          {/* Bottom bar */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-4 px-4 pb-4 h-72">
            <NotesPanel
              notes={notes}
              isGenerating={isGeneratingNotes}
              lectureCompleted={isCompleted}
            />
            <ChatPanel
              messages={chatMessages}
              onSend={handleQuestion}
              disabled={!lecture}
            />
          </section>
        </>
      )}
    </div>
  )
}
