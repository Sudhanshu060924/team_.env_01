'use client'

import { useEffect, useId, useCallback, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Lecture, LectureEvent } from '@/types/lecture'
import {
  TargetLanguage,
  TopicState,
  ImportantEvent,
  ChatMessage,
  TranslationLine,
} from '@/types/ai'
import { ChatMessageRead } from '@/types/chat'
import { TranscriptLine } from '@/components/lecture/TranscriptPanel'
import LectureLayout from '@/components/lecture/LectureLayout'
import AppShell from '@/components/layout/AppShell'
import Badge from '@/components/ui/Badge'

// ── Helpers ──────────────────────────────────────────────────────────────────

function eventToTranscriptLine(e: LectureEvent): TranscriptLine {
  return {
    timestamp: e.timestamp,
    text: e.content,
    language: (e.metadata?.language as string) ?? 'en',
  }
}

function eventToTranslationLine(e: LectureEvent): TranslationLine {
  return {
    timestamp: e.timestamp,
    content: e.content,
    language: ((e.metadata?.language as string) ?? 'english') as TargetLanguage,
    source: e.source,
  }
}

function eventToTopicState(e: LectureEvent): TopicState {
  return {
    topic: e.content,
    subtopic: (e.metadata?.subtopic as string) ?? '',
    timestamp: e.timestamp,
  }
}

function eventToImportantEvent(e: LectureEvent, uid: string): ImportantEvent {
  return {
    id: `${uid}-${e.event_id}`,
    timestamp: e.timestamp,
    content: e.content,
    isFormula: !!(e.metadata?.is_formula as boolean),
  }
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function StudentLecturePage() {
  const { lectureId } = useParams<{ lectureId: string }>()
  const router = useRouter()
  const { isLoading: authLoading, isAuthenticated } = useAuth()
  const uid = useId()
  const videoRef = useRef<HTMLVideoElement>(null)

  const [pageLoading, setPageLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [lecture, setLecture] = useState<Lecture | null>(null)

  const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[]>([])
  const [translationLines, setTranslationLines] = useState<TranslationLine[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState<TargetLanguage>('english')
  const [topic, setTopic] = useState<TopicState | null>(null)
  const [importantEvents, setImportantEvents] = useState<ImportantEvent[]>([])
  const [notes, setNotes] = useState<string | null>(null)
  const [notesLanguage, setNotesLanguage] = useState<TargetLanguage>('english')
  const [chatMessages] = useState<ChatMessage[]>([])

  const [doubtMessages, setDoubtMessages] = useState<ChatMessageRead[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [isDoubtSending, setIsDoubtSending] = useState(false)
  const [doubtSendError, setDoubtSendError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seenMessageIds = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [authLoading, isAuthenticated, router])

  useEffect(() => {
    if (!isAuthenticated || !lectureId) return
    let cancelled = false

    async function loadLecture() {
      try {
        const lec = await api.getStudentLecture(lectureId)
        if (cancelled) return
        setLecture(lec)

        const [speechEvents, translationEvents, topicEvents, importantEventsList] =
          await Promise.all([
            api.getEvents(lectureId, 'speech_event'),
            api.getEvents(lectureId, 'translation'),
            api.getEvents(lectureId, 'topic_update'),
            api.getEvents(lectureId, 'important_event'),
          ])
        if (cancelled) return

        setTranscriptLines(speechEvents.map(eventToTranscriptLine))
        setTranslationLines(
          translationEvents
            .filter((e) => (e.metadata?.language as string) === 'english')
            .map(eventToTranslationLine)
        )

        if (topicEvents.length > 0) {
          setTopic(eventToTopicState(topicEvents[topicEvents.length - 1]))
        }

        setImportantEvents(importantEventsList.map((e) => eventToImportantEvent(e, uid)))

        try {
          const notesData = await api.getNotes(lectureId, 'english')
          if (!cancelled && notesData.length > 0) {
            setNotes(notesData[0].content)
          }
        } catch {
          // Notes may not exist yet
        }

        try {
          const thread = await api.getStudentChat(lectureId)
          if (!cancelled) {
            setThreadId(thread.thread_id)
            const sorted = [...thread.messages].sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            sorted.forEach((m) => seenMessageIds.current.add(m.id))
            setDoubtMessages(sorted)
          }
        } catch {
          // Doubts not available yet
        }
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load lecture'
          if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
            setPageError('Lecture not found.')
          } else if (msg.includes('403') || msg.toLowerCase().includes('forbidden')) {
            setPageError("You don't have access to this lecture.")
          } else {
            setPageError(msg)
          }
        }
      } finally {
        if (!cancelled) setPageLoading(false)
      }
    }

    loadLecture()
    return () => { cancelled = true }
  }, [isAuthenticated, lectureId, uid])

  const handleLanguageChange = useCallback(
    async (lang: TargetLanguage) => {
      setSelectedLanguage(lang)
      if (!lectureId) return
      try {
        const events = await api.getEvents(lectureId, 'translation')
        setTranslationLines(
          events
            .filter((e) => (e.metadata?.language as string) === lang)
            .map(eventToTranslationLine)
        )
      } catch {
        // ignore
      }
    },
    [lectureId]
  )

  const handleNotesLanguageChange = useCallback(
    async (lang: TargetLanguage) => {
      setNotesLanguage(lang)
      if (!lectureId) return
      try {
        const notesData = await api.getNotes(lectureId, lang)
        if (notesData.length > 0) {
          setNotes(notesData[0].content)
        } else {
          setNotes(null)
        }
      } catch {
        // ignore
      }
    },
    [lectureId]
  )

  const handleVideoEnded = useCallback(() => {}, [])
  const handleChatSend = useCallback(() => {}, [])

  const connectDoubtsWS = useCallback(() => {
    if (!lectureId || !isAuthenticated) return
    const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'
    const token = document.cookie
      .split('; ')
      .find((c) => c.startsWith('session_token='))
      ?.split('=')[1]
    const url = `${WS_BASE}/ws/lectures/${lectureId}${token ? `?token=${token}` : ''}`

    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close()
    }

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'chat_message_created' && msg.message) {
          const m = msg.message as ChatMessageRead
          if (!seenMessageIds.current.has(m.id)) {
            seenMessageIds.current.add(m.id)
            setDoubtMessages((prev) => {
              const updated = [...prev, m]
              updated.sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              )
              return updated
            })
          }
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      reconnectTimerRef.current = setTimeout(() => { connectDoubtsWS() }, 3000)
    }
    ws.onerror = () => { ws.close() }
  }, [lectureId, isAuthenticated])

  useEffect(() => {
    if (!isAuthenticated || !lectureId) return
    connectDoubtsWS()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [isAuthenticated, lectureId, connectDoubtsWS])

  const handleDoubtSend = useCallback(
    async (content: string) => {
      if (!lectureId || isDoubtSending) return
      setIsDoubtSending(true)
      setDoubtSendError(null)
      try {
        const msg = await api.postStudentMessage(lectureId, content)
        if (!seenMessageIds.current.has(msg.id)) {
          seenMessageIds.current.add(msg.id)
          setDoubtMessages((prev) => {
            const updated = [...prev, msg]
            updated.sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            return updated
          })
          if (!threadId) setThreadId(msg.thread_id)
        }
      } catch (err) {
        setDoubtSendError(err instanceof Error ? err.message : 'Failed to send message')
      } finally {
        setIsDoubtSending(false)
      }
    },
    [lectureId, threadId, isDoubtSending]
  )

  // ── Loading / error states ───────────────────────────────────────────────
  if (authLoading || (pageLoading && !pageError)) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        {authLoading ? 'Loading…' : 'Loading lecture…'}
      </div>
    )
  }

  if (pageError) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-gray-700">{pageError}</p>
        <button
          onClick={() => router.push('/student/dashboard')}
          className="text-xs font-semibold border border-gray-300 rounded px-3 py-1.5 hover:border-gray-400 transition-colors text-gray-700"
        >
          ← Back to lectures
        </button>
      </div>
    )
  }

  return (
    /*
     * h-screen + overflow-hidden: the lecture page NEVER scrolls at the
     * browser/window level. All scrolling happens inside individual panels.
     */
    <div className="h-screen overflow-hidden flex flex-col bg-white">
      {/* ── Lecture top bar (replaces AppShell to keep layout tight) ── */}
      <header className="flex items-center justify-between px-4 h-12 border-b border-gray-200 shrink-0 bg-white z-10">
        {/* Left: back + title */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => router.push('/student/dashboard')}
            className="text-gray-500 hover:text-gray-800 p-1 rounded transition-colors shrink-0"
            aria-label="Back to lectures"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.jpg" alt="" className="w-6 h-6 rounded-full object-cover hidden sm:block border border-gray-200" />
          <span className="font-bold text-sm text-black whitespace-nowrap">VidyaRoom</span>
          {lecture?.title && (
            <span className="text-sm text-gray-600 truncate hidden md:block">{lecture.title}</span>
          )}
          {lecture?.status === 'completed' && (
            <Badge variant="completed">Completed</Badge>
          )}
          {lecture?.status === 'live' && (
            <Badge variant="live">● Live</Badge>
          )}
        </div>

        {/* Right: back button text on larger screens */}
        <button
          onClick={() => router.push('/student/dashboard')}
          className="text-xs font-semibold text-gray-600 hover:text-black border border-gray-200 rounded px-3 py-1.5 transition-colors hover:border-gray-400 hidden sm:flex items-center gap-1"
        >
          ← My Lectures
        </button>
      </header>

      {/* ── Lecture content (fills remaining h-screen height, no overflow) ── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        <LectureLayout
          videoRef={videoRef}
          videoSrc={lecture?.video_url ?? null}
          onVideoEnded={handleVideoEnded}
          transcriptLines={transcriptLines}
          translationLines={translationLines}
          selectedLanguage={selectedLanguage}
          onLanguageChange={handleLanguageChange}
          topic={topic}
          importantEvents={importantEvents}
          notes={notes}
          isGeneratingNotes={false}
          isRegeneratingNotes={false}
          notesError={null}
          notesLanguage={notesLanguage}
          onNotesLanguageChange={handleNotesLanguageChange}
          chatMessages={chatMessages}
          onChatSend={handleChatSend}
          isLive={false}
          isCompleted={true}
          lectureTitle={lecture?.title ?? ''}
          doubtMessages={doubtMessages}
          onDoubtSend={handleDoubtSend}
          isDoubtSending={isDoubtSending}
          doubtSendError={doubtSendError}
          showDoubts={true}
        />
      </div>
    </div>
  )
}
