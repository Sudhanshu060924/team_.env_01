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
  TranslationLine,
  TranscriptChunk,
} from '@/types/ai'
import { ChatMessageRead } from '@/types/chat'
import LectureLayout from '@/components/lecture/LectureLayout'
import Badge from '@/components/ui/Badge'

// ── Helpers ──────────────────────────────────────────────────────────────────

function eventToTranscriptChunk(e: LectureEvent): TranscriptChunk {
  const start = (e.metadata?.start as number) ?? e.timestamp
  const end   = (e.metadata?.end   as number) ?? e.timestamp
  return {
    timestamp: start,
    start,
    end,
    content: e.content,
    language: (e.metadata?.language as string) ?? 'en',
  }
}

function eventToTranslationLine(e: LectureEvent): TranslationLine {
  const start = (e.metadata?.start as number) ?? e.timestamp
  const end   = (e.metadata?.end   as number) ?? e.timestamp
  return {
    timestamp: start,
    start,
    end,
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

  const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([])
  const [translationLines, setTranslationLines] = useState<TranslationLine[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState<TargetLanguage>('english')
  const [topics, setTopics] = useState<TopicState[]>([])
  const [importantEvents, setImportantEvents] = useState<ImportantEvent[]>([])
  const [notes, setNotes] = useState<string | null>(null)
  const [notesLanguage, setNotesLanguage] = useState<TargetLanguage>('english')
  // true while backend is generating notes
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false)
  const [notesError, setNotesError] = useState<string | null>(null)
  // true when the pipeline completed but found no speech in the video
  const [noSpeechDetected, setNoSpeechDetected] = useState(false)
  // ── AI Chat state (Chat tab: student ↔ AI chatbot) ───────────────────────
  const [aiChatMessages, setAiChatMessages] = useState<ChatMessageRead[]>([])
  const [isAiChatSending, setIsAiChatSending] = useState(false)
  const [aiChatError, setAiChatError] = useState<string | null>(null)

  // ── Doubts state (Doubts tab: student ↔ teacher) ─────────────────────────
  const [doubtMessages, setDoubtMessages] = useState<ChatMessageRead[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [isDoubtSending, setIsDoubtSending] = useState(false)
  const [doubtSendError, setDoubtSendError] = useState<string | null>(null)

  // Stable refs so WS callbacks always see current values without being
  // included in the useEffect dependency array.
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seenMessageIds = useRef<Set<string>>(new Set())
  // Tracks whether the current WS effect has been cleaned up (unmount / lectureId change)
  const wsDestroyedRef = useRef(false)
  // Ref to always access current language values inside stable WS callbacks
  const selectedLanguageRef = useRef<TargetLanguage>('english')
  const notesLanguageRef = useRef<TargetLanguage>('english')
  const uidRef = useRef(uid)
  // Ref holding the latest handleWsMessage so ws.onmessage always dispatches
  // to the current function even though the WS effect only runs once.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleWsMessageRef = useRef<(msg: Record<string, unknown>) => void>(() => {})

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [authLoading, isAuthenticated, router])

  // ── Video seek handler ───────────────────────────────────────────────────
  const handleSeek = useCallback((seconds: number) => {
    const video = videoRef.current
    if (video) {
      video.currentTime = seconds
      // If paused and seek is requested, optionally start playing
      // (comment out the next line if you want seek-only without auto-play)
      // video.play()
    }
  }, [])

  // ── Load lecture data once ───────────────────────────────────────────────
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

        // Populate transcript chunks from stored speech_events
        if (speechEvents.length > 0) {
          setTranscriptChunks(speechEvents.map(eventToTranscriptChunk))
        }

        // Show English translations by default
        setTranslationLines(
          translationEvents
            .filter((e) => (e.metadata?.language as string) === 'english')
            .map(eventToTranslationLine)
        )

        if (topicEvents.length > 0) {
          setTopics(topicEvents.map(eventToTopicState))
        }

        setImportantEvents(importantEventsList.map((e) => eventToImportantEvent(e, uid)))

        // Load AI chat history (Chat tab) — non-blocking
        try {
          const aiThread = await api.getAIChat(lectureId)
          if (!cancelled) {
            const sorted = [...aiThread.messages].sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            setAiChatMessages(sorted)
          }
        } catch {
          // AI chat thread not available yet — non-fatal
        }

        // Load doubts history (Doubts tab: student+teacher only) — non-blocking
        try {
          const doubtThread = await api.getStudentDoubts(lectureId)
          if (!cancelled) {
            setThreadId(doubtThread.thread_id)
            const sorted = [...doubtThread.messages].sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            sorted.forEach((m) => seenMessageIds.current.add(m.id))
            setDoubtMessages(sorted)
          }
        } catch {
          // Doubts thread not available yet — non-fatal
        }

        // Trigger processing (idempotent — backend returns immediately if already
        // running or completed with events present)
        if (lec.video_url) {
          try {
            await api.processLecture(lectureId)
          } catch {
            // Processing start failure is non-fatal
          }
        }

        // Fetch existing notes (english by default). If not found the WS pipeline
        // will broadcast them when ready; show spinner in the meantime.
        try {
          const notesData = await api.getNotes(lectureId, 'english')
          if (!cancelled) {
            if (notesData.length > 0) {
              setNotes(notesData[0].content)
              setIsGeneratingNotes(false)
            } else {
              // Notes not yet available — show spinner; they will arrive via WS.
              setIsGeneratingNotes(true)
            }
          }
        } catch {
          // Notes fetch failed — non-fatal
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

  // ── WebSocket — stable effect, only depends on lectureId ─────────────────
  useEffect(() => {
    if (!isAuthenticated || !lectureId) return

    wsDestroyedRef.current = false

    const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'

    function connect() {
      if (wsDestroyedRef.current) return

      const token = document.cookie
        .split('; ')
        .find((c) => c.startsWith('session_token='))
        ?.split('=')[1]
      const url = `${WS_BASE}/ws/lectures/${lectureId}${token ? `?token=${token}` : ''}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string)
          handleWsMessageRef.current(msg)
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        ws.close()
      }

      ws.onclose = () => {
        if (!wsDestroyedRef.current) {
          reconnectTimerRef.current = setTimeout(connect, 3000)
        }
      }
    }

    connect()

    return () => {
      wsDestroyedRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lectureId])

  // ── WebSocket message handler ────────────────────────────────────────────
  function handleWsMessage(msg: Record<string, unknown>) {
    const type = msg.type as string

    if (type === 'connected') return

    // Incoming transcript chunk from pipeline
    if (type === 'transcript' || type === 'speech_event') {
      const content   = (msg.content as string) ?? ''
      const timestamp = (msg.timestamp as number) ?? 0
      const start     = (msg.start as number) ?? timestamp
      const end       = (msg.end as number) ?? timestamp
      const language  = ((msg.metadata as Record<string, unknown>)?.language as string) ?? 'en'
      if (content) {
        setTranscriptChunks((prev) => {
          // Avoid duplicates (pipeline may resend on reconnect)
          if (prev.some((c) => Math.abs(c.start - start) < 0.1 && c.content === content)) {
            return prev
          }
          return [...prev, { timestamp: start, start, end, content, language }]
            .sort((a, b) => a.start - b.start)
        })
      }
      return
    }

    if (type === 'translation') {
      const content   = (msg.content as string) ?? ''
      const timestamp = (msg.timestamp as number) ?? 0
      const start     = (msg.start as number) ?? timestamp
      const end       = (msg.end as number) ?? timestamp
      const meta      = (msg.metadata as Record<string, unknown>) ?? {}
      const lang      = ((msg.language as string) || (meta.language as string)) ?? 'english'
      const source    = (msg.source as string) ?? 'translation_agent'
      if (content) {
        if (lang === selectedLanguageRef.current) {
          setTranslationLines((prev) => {
            // Avoid duplicates
            if (prev.some((l) => Math.abs(l.start - start) < 0.1 && l.content === content)) {
              return prev
            }
            return [...prev, { timestamp: start, start, end, content, language: lang as TargetLanguage, source }]
              .sort((a, b) => a.start - b.start)
          })
        }
      }
      return
    }

    if (type === 'topic_update') {
      const content   = (msg.content as string) ?? ''
      const timestamp = (msg.timestamp as number) ?? 0
      const subtopic  = ((msg.metadata as Record<string, unknown>)?.subtopic as string) ?? ''
      if (content) {
        setTopics((prev) => {
          // Avoid exact duplicates
          if (prev.some((t) => t.topic === content && t.timestamp === timestamp)) return prev
          return [...prev, { topic: content, subtopic, timestamp }]
            .sort((a, b) => a.timestamp - b.timestamp)
        })
      }
      return
    }

    if (type === 'important_event') {
      const content   = (msg.content as string) ?? ''
      const timestamp = (msg.timestamp as number) ?? 0
      const isFormula = !!((msg.metadata as Record<string, unknown>)?.is_formula)
      if (content) {
        const id = `${uidRef.current}-ws-${Date.now()}-${Math.random()}`
        setImportantEvents((prev) => {
          if (prev.some((e) => e.content === content && e.timestamp === timestamp)) return prev
          return [...prev, { id, timestamp, content, isFormula }]
            .sort((a, b) => a.timestamp - b.timestamp)
        })
      }
      return
    }

    if (type === 'notes') {
      const content  = (msg.content as string) ?? ''
      const language = (msg.language as string) ?? 'english'
      if (content) {
        if (language === notesLanguageRef.current) {
          setNotes(content)
          setIsGeneratingNotes(false)
          setNotesError(null)
        }
      }
      return
    }

    if (type === 'notes_generating') {
      const language = (msg.language as string) ?? 'english'
      if (language === notesLanguageRef.current) {
        setIsGeneratingNotes(true)
        setNotesError(null)
      }
      return
    }

    if (type === 'processing_status') {
      const stage = (msg.stage as string) ?? ''
      if (stage === 'notes') {
        setIsGeneratingNotes(true)
        setNotesError(null)
      }
      if (stage === 'transcription_empty') {
        setIsGeneratingNotes(false)
        setNoSpeechDetected(true)
      }
      return
    }

    if (type === 'processing_error') {
      const stage = (msg.stage as string) ?? ''
      if (stage === 'notes') {
        setIsGeneratingNotes(false)
        setNotesError('Notes generation failed. Please try again.')
      }
      return
    }

    if (type === 'lecture_completed') {
      setLecture((prev) => prev ? { ...prev, status: 'completed' } : prev)
      if (notesLanguageRef.current && lectureId) {
        api.getNotes(lectureId, notesLanguageRef.current)
          .then((notesData) => {
            if (notesData.length > 0) {
              setNotes(notesData[0].content)
              setIsGeneratingNotes(false)
              setNotesError(null)
            } else {
              setIsGeneratingNotes(false)
            }
          })
          .catch(() => {
            setIsGeneratingNotes(false)
          })
      } else {
        setIsGeneratingNotes(false)
      }
      return
    }

    if (type === 'chat_message_created' && msg.message) {
      const m = msg.message as ChatMessageRead
      if (!seenMessageIds.current.has(m.id)) {
        seenMessageIds.current.add(m.id)
        if (m.sender_role === 'ai') {
          // AI messages belong to the Chat tab only
          setAiChatMessages((prev) => {
            const updated = [...prev, m]
            updated.sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            return updated
          })
        } else {
          // student/teacher messages belong to the Doubts tab only
          setDoubtMessages((prev) => {
            const updated = [...prev, m]
            updated.sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            return updated
          })
        }
      }
      return
    }

    if (type === 'error') {
      const message = (msg.message as string) ?? ''
      if (message.toLowerCase().includes('notes')) {
        setIsGeneratingNotes(false)
        setNotesError(message)
      }
      return
    }
  }
  handleWsMessageRef.current = handleWsMessage

  // ── Send a message through the open WebSocket ─────────────────────────────
  function sendWsMessage(payload: Record<string, unknown>) {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload))
    }
  }

  // ── Translation language change ──────────────────────────────────────────
  const handleLanguageChange = useCallback(
    async (lang: TargetLanguage) => {
      selectedLanguageRef.current = lang
      setSelectedLanguage(lang)
      if (!lectureId) return

      try {
        // 1. Try to show existing translated events from the DB
        const events = await api.getEvents(lectureId, 'translation')
        const filtered = events.filter((e) => (e.metadata?.language as string) === lang)

        if (filtered.length > 0) {
          setTranslationLines(filtered.map(eventToTranslationLine))
        } else {
          // 2. No existing translation for this language — clear panel and
          //    request retranslation via WebSocket
          setTranslationLines([])
          sendWsMessage({
            type: 'language_change',
            lecture_id: lectureId,
            target_language: lang,
          })
        }
      } catch {
        setTranslationLines([])
        sendWsMessage({
          type: 'language_change',
          lecture_id: lectureId,
          target_language: lang,
        })
      }
    },
    [lectureId]
  )

  // ── Notes language change ────────────────────────────────────────────────
  const handleNotesLanguageChange = useCallback(
    async (lang: TargetLanguage) => {
      notesLanguageRef.current = lang
      setNotesLanguage(lang)
      setNotesError(null)
      if (!lectureId) return

      try {
        const notesData = await api.getNotes(lectureId, lang)
        if (notesData.length > 0) {
          setNotes(notesData[0].content)
          setIsGeneratingNotes(false)
        } else {
          setNotes(null)
          setIsGeneratingNotes(true)
          sendWsMessage({
            type: 'generate_notes',
            lecture_id: lectureId,
            target_language: lang,
          })
        }
      } catch {
        setNotes(null)
        setIsGeneratingNotes(true)
        sendWsMessage({
          type: 'generate_notes',
          lecture_id: lectureId,
          target_language: lang,
        })
      }
    },
    [lectureId]
  )

  const handleVideoEnded = useCallback(() => {}, [])

  // ── Chat tab: send a question to the AI chatbot ──────────────────────────
  const handleChatSend = useCallback(
    async (content: string) => {
      if (!lectureId || isAiChatSending) return
      setIsAiChatSending(true)
      setAiChatError(null)
      try {
        const response = await api.askAI(lectureId, content)
        const { student_message: studentMsg, ai_message: aiMsg } = response
        setAiChatMessages((prev) => {
          const ids = new Set(prev.map((m) => m.id))
          const toAdd = [studentMsg, aiMsg].filter((m) => !ids.has(m.id))
          if (toAdd.length === 0) return prev
          const updated = [...prev, ...toAdd]
          updated.sort(
            (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          )
          return updated
        })
      } catch (err) {
        setAiChatError(err instanceof Error ? err.message : 'Failed to get AI response')
      } finally {
        setIsAiChatSending(false)
      }
    },
    [lectureId, isAiChatSending]
  )

  // ── Doubts tab: send a doubt to the teacher (no AI) ──────────────────────
  const handleDoubtSend = useCallback(
    async (content: string) => {
      if (!lectureId || isDoubtSending) return
      setIsDoubtSending(true)
      setDoubtSendError(null)
      try {
        const studentMsg = await api.sendDoubt(lectureId, content)
        if (!seenMessageIds.current.has(studentMsg.id)) {
          seenMessageIds.current.add(studentMsg.id)
          setDoubtMessages((prev) => {
            const updated = [...prev, studentMsg]
            updated.sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            )
            return updated
          })
        }
        if (!threadId) setThreadId(studentMsg.thread_id)
      } catch (err) {
        setDoubtSendError(err instanceof Error ? err.message : 'Failed to send doubt')
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
    <div className="h-screen overflow-hidden flex flex-col bg-white">
      {/* ── Lecture top bar ── */}
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
          {lecture?.status === 'available' && (
            <Badge variant="completed">Available</Badge>
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

      {/* ── Lecture content (fills remaining h-screen height) ── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        <LectureLayout
          videoRef={videoRef}
          videoSrc={lecture?.video_url ?? null}
          onVideoEnded={handleVideoEnded}
          onSeek={handleSeek}
          transcriptChunks={transcriptChunks}
          translationLines={translationLines}
          selectedLanguage={selectedLanguage}
          onLanguageChange={handleLanguageChange}
          topics={topics}
          importantEvents={importantEvents}
          notes={notes}
          isGeneratingNotes={isGeneratingNotes}
          notesError={notesError}
          notesLanguage={notesLanguage}
          onNotesLanguageChange={handleNotesLanguageChange}
          aiChatMessages={aiChatMessages}
          onChatSend={handleChatSend}
          isAiChatSending={isAiChatSending}
          aiChatError={aiChatError}
          isLive={lecture?.status === 'live'}
          isCompleted={lecture?.status === 'completed' || lecture?.status === 'available'}
          lectureTitle={lecture?.title ?? ''}
          noSpeechDetected={noSpeechDetected}
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
