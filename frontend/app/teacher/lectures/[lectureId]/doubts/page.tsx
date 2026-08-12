'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { TeacherThreadRead, ChatMessageRead } from '@/types/chat'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import Button from '@/components/ui/Button'
import Avatar from '@/components/ui/Avatar'

export default function TeacherLectureDoubtsPage() {
  const { lectureId } = useParams<{ lectureId: string }>()
  const router = useRouter()
  const { user, isLoading: authLoading, isAuthenticated } = useAuth()

  const [threads, setThreads] = useState<TeacherThreadRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [replyInput, setReplyInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seenMessageIds = useRef<Set<string>>(new Set())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login')
    }
    if (!authLoading && isAuthenticated && user?.role !== 'teacher') {
      router.replace('/student/dashboard')
    }
  }, [authLoading, isAuthenticated, user, router])

  const loadThreads = useCallback(async () => {
    if (!lectureId) return
    try {
      const data = await api.getTeacherChat(lectureId)
      setThreads(data)
      data.forEach((t) => t.messages.forEach((m) => seenMessageIds.current.add(m.id)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load doubts')
    } finally {
      setLoading(false)
    }
  }, [lectureId])

  useEffect(() => {
    if (!isAuthenticated) return
    loadThreads()
  }, [isAuthenticated, loadThreads])

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeThreadId, threads])

  const connectWS = useCallback(() => {
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
          if (seenMessageIds.current.has(m.id)) return
          seenMessageIds.current.add(m.id)

          setThreads((prev) => {
            const idx = prev.findIndex((t) => t.thread_id === m.thread_id)
            if (idx === -1) {
              loadThreads()
              return prev
            }
            const updated = [...prev]
            updated[idx] = {
              ...updated[idx],
              messages: [...updated[idx].messages, m].sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              ),
            }
            return updated
          })
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      reconnectTimerRef.current = setTimeout(connectWS, 3000)
    }
    ws.onerror = () => ws.close()
  }, [lectureId, isAuthenticated, loadThreads])

  useEffect(() => {
    if (!isAuthenticated || !lectureId) return
    connectWS()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [isAuthenticated, lectureId, connectWS])

  const handleReply = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!lectureId || !activeThreadId || !replyInput.trim() || isSending) return
      setIsSending(true)
      setSendError(null)
      try {
        const msg = await api.postTeacherReply(lectureId, activeThreadId, replyInput.trim())
        setReplyInput('')
        if (!seenMessageIds.current.has(msg.id)) {
          seenMessageIds.current.add(msg.id)
          setThreads((prev) => {
            const idx = prev.findIndex((t) => t.thread_id === activeThreadId)
            if (idx === -1) return prev
            const updated = [...prev]
            updated[idx] = {
              ...updated[idx],
              messages: [...updated[idx].messages, msg].sort(
                (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
              ),
            }
            return updated
          })
        }
      } catch (err) {
        setSendError(err instanceof Error ? err.message : 'Failed to send reply')
      } finally {
        setIsSending(false)
      }
    },
    [lectureId, activeThreadId, replyInput, isSending]
  )

  const activeThread = threads.find((t) => t.thread_id === activeThreadId) ?? null

  if (authLoading || (loading && !error)) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        {authLoading ? 'Loading…' : 'Loading student doubts…'}
      </div>
    )
  }

  if (!user) return null

  return (
    <AppShell role="teacher">
      <AppHeader
        title="Student Doubts"
        subtitle="Review and respond to student questions"
      />

      <div className="flex-1 overflow-hidden flex flex-col min-h-0 px-6 py-6">
        {error && (
          <p className="text-sm text-red-600 border border-red-200 bg-red-50 px-4 py-3 rounded mb-4">
            {error}
          </p>
        )}

        {!error && threads.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-500">
            No student doubts yet for this lecture.
          </div>
        )}

        {threads.length > 0 && (
          <div className="flex gap-5 flex-1 min-h-0 overflow-hidden">
            {/* ── Thread list ── */}
            <div className="w-60 shrink-0 flex flex-col gap-1 overflow-y-auto pr-1">
              <p className="text-[11px] uppercase tracking-widest text-gray-500 font-semibold mb-2 px-1">
                Students ({threads.length})
              </p>
              {threads.map((t) => {
                const unanswered = t.messages.every((m) => m.sender_role === 'student')
                const isActive = activeThreadId === t.thread_id
                return (
                  <button
                    key={t.thread_id}
                    onClick={() => {
                      setActiveThreadId(t.thread_id)
                      setReplyInput('')
                      setSendError(null)
                    }}
                    className={[
                      'w-full text-left px-3 py-3 border rounded-lg text-sm transition-colors',
                      isActive
                        ? 'border-yellow-400 bg-yellow-50 font-semibold'
                        : 'border-gray-200 hover:border-gray-300 bg-white',
                    ].join(' ')}
                  >
                    <div className="flex items-center gap-2">
                      <Avatar name={t.student.name} size="sm" />
                      <div className="min-w-0">
                        <span className="block font-medium text-black text-sm truncate">
                          {t.student.name}
                        </span>
                        <span className="block text-xs text-gray-500">
                          {t.messages.length} message{t.messages.length !== 1 ? 's' : ''}
                          {unanswered && t.messages.length > 0 && (
                            <span className="ml-1.5 text-yellow-600 font-semibold">· Unanswered</span>
                          )}
                        </span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* ── Active thread ── */}
            <div className="flex-1 flex flex-col min-h-0 border border-gray-200 rounded-lg overflow-hidden bg-white">
              {!activeThread ? (
                <div className="flex-1 flex items-center justify-center text-sm text-gray-500 italic p-8">
                  Select a student to view their doubts.
                </div>
              ) : (
                <>
                  {/* Thread header */}
                  <div className="border-b border-gray-200 px-5 py-3 shrink-0 flex items-center gap-3">
                    <Avatar name={activeThread.student.name} size="sm" />
                    <div>
                      <span className="font-semibold text-sm text-black">
                        {activeThread.student.name}
                      </span>
                      <span className="text-xs text-gray-500 ml-2">
                        {activeThread.messages.length} message{activeThread.messages.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
                    {activeThread.messages.length === 0 && (
                      <p className="text-sm text-gray-500 italic">No messages yet.</p>
                    )}
                    {activeThread.messages.map((msg) => {
                      const isStudent = msg.sender_role === 'student'
                      return (
                        <div
                          key={msg.id}
                          className={['flex gap-2.5', isStudent ? 'flex-row' : 'flex-row-reverse'].join(' ')}
                        >
                          <Avatar name={isStudent ? activeThread.student.name : user.name} size="sm" />
                          <div className={['flex flex-col gap-1 max-w-[75%]', isStudent ? 'items-start' : 'items-end'].join(' ')}>
                            <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
                              {isStudent ? activeThread.student.name : 'You (Teacher)'}
                            </span>
                            <div
                              className={[
                                'px-3 py-2 text-sm leading-relaxed rounded-lg',
                                isStudent
                                  ? 'bg-gray-100 text-black border border-gray-200'
                                  : 'bg-yellow-400 text-black',
                              ].join(' ')}
                            >
                              {msg.content}
                            </div>
                            <span className="text-[10px] text-gray-400">
                              {new Date(msg.created_at).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                    <div ref={messagesEndRef} />
                  </div>

                  {/* Reply input */}
                  <div className="border-t border-gray-200 p-4 shrink-0">
                    {sendError && (
                      <p className="text-xs text-red-600 mb-2">{sendError}</p>
                    )}
                    <form onSubmit={handleReply} className="flex gap-2">
                      <input
                        type="text"
                        value={replyInput}
                        onChange={(e) => setReplyInput(e.target.value)}
                        placeholder="Reply to student…"
                        disabled={isSending}
                        className="flex-1 bg-white text-black text-sm border border-gray-300 rounded px-3 py-2 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 placeholder-gray-400 disabled:opacity-40 transition-colors"
                      />
                      <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        loading={isSending}
                        disabled={!replyInput.trim()}
                      >
                        Reply
                      </Button>
                    </form>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
