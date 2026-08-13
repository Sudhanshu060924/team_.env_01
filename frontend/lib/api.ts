import { Lecture, LectureCreate, LectureEvent } from '@/types/lecture'
import { ChatThreadRead, TeacherThreadRead, ChatMessageRead, AIChatResponse, LectureDoubtAnalytics } from '@/types/chat'
import {
  FeedbackOverview,
  FeedbackTopic,
  RatingRead,
  RatingCreate,
  RatingAnalytics,
  WrittenReview,
  LectureEngagementStats,
  ProblemSolvingStats,
  TeacherPerformanceScore,
  PlaybackFlush,
} from '@/types/feedback'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include', // always send session cookie
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

/** Multipart upload — does NOT set Content-Type so the browser sets it with boundary. */
async function uploadFile<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () =>
    request<{ status: string; service: string }>('/health'),

  /** All lectures — unrestricted (legacy) */
  listLectures: () =>
    request<Lecture[]>('/lectures'),

  /** Completed lectures accessible to the authenticated student */
  listStudentLectures: () =>
    request<Lecture[]>('/lectures/student/lectures'),

  /** Lectures owned by the authenticated teacher */
  listTeacherLectures: () =>
    request<Lecture[]>('/lectures/teacher/lectures'),

  startLecture: (payload: LectureCreate) =>
    request<Lecture>('/lectures/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getLecture: (lectureId: string) =>
    request<Lecture>(`/lectures/${lectureId}`),

  /** Get a completed lecture, verified for student access */
  getStudentLecture: (lectureId: string) =>
    request<Lecture>(`/lectures/student/lectures/${lectureId}`),

  completeLecture: (lectureId: string) =>
    request<Lecture>(`/lectures/${lectureId}/complete`, { method: 'POST' }),

  getEvents: (lectureId: string, type?: string) =>
    request<LectureEvent[]>(`/lectures/${lectureId}/events${type ? `?type=${type}` : ''}`),

  getNotes: (lectureId: string, language?: string) =>
    request<{ note_id: string; lecture_id: string; content: string; language: string; created_at: string }[]>(
      `/lectures/${lectureId}/notes${language ? `?language=${language}` : ''}`
    ),

  /** Upload a video file for a lecture (teacher only). Returns updated lecture. */
  uploadLectureVideo: (lectureId: string, file: File) => {
    const form = new FormData()
    form.append('video', file)
    return uploadFile<Lecture>(`/lectures/${lectureId}/video`, form)
  },

  askQuestion: (lectureId: string, question: string) =>
    request<{ answer: string; sources: string[] }>(
      `/lectures/${lectureId}/questions`,
      {
        method: 'POST',
        body: JSON.stringify({ question }),
      }
    ),

  /**
   * Start (or reuse) the processing pipeline for a pre-recorded lecture.
   * Idempotent — safe to call even if processing is already running or done.
   */
  processLecture: (lectureId: string) =>
    request<{ status: string; lecture_id: string }>(
      `/lectures/${lectureId}/process`,
      { method: 'POST' }
    ),

  // ── Student AI chat endpoints (Chat tab: student ↔ AI) ─────────────────

  /** Get the authenticated student's full AI chat thread for this lecture */
  getAIChat: (lectureId: string) =>
    request<ChatThreadRead>(`/lectures/${lectureId}/chat`),

  /**
   * Post a student question to the AI chatbot.
   * Returns both the student message and the AI reply.
   */
  askAI: (lectureId: string, content: string) =>
    request<AIChatResponse>(`/lectures/${lectureId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  // ── Student doubt endpoints (Doubts tab: student ↔ teacher) ────────────

  /**
   * Get the student's doubt thread (only student + teacher messages, no AI).
   */
  getStudentDoubts: (lectureId: string) =>
    request<ChatThreadRead>(`/lectures/${lectureId}/doubts`),

  /**
   * Post a student doubt to the teacher (does NOT call the AI chatbot).
   * Returns the saved student message only.
   */
  sendDoubt: (lectureId: string, content: string) =>
    request<ChatMessageRead>(`/lectures/${lectureId}/doubts`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  // ── Teacher chat endpoints ──────────────────────────────────────────────

  /** Get all student threads for a lecture owned by this teacher */
  getTeacherChat: (lectureId: string) =>
    request<TeacherThreadRead[]>(`/lectures/teacher/lectures/${lectureId}/chat`),

  /** Post a teacher reply to a specific student thread */
  postTeacherReply: (lectureId: string, threadId: string, content: string) =>
    request<ChatMessageRead>(
      `/lectures/teacher/lectures/${lectureId}/chat/${threadId}`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      }
    ),

  /** Get teacher doubt analytics for a lecture (anonymized, teacher-only) */
  getDoubtAnalytics: (lectureId: string) =>
    request<LectureDoubtAnalytics>(
      `/lectures/teacher/lectures/${lectureId}/chat/analytics`
    ),

  // ── Teacher feedback / analytics endpoints ─────────────────────────────

  /** Get aggregated feedback overview (all lectures, or one if lectureId given) */
  getFeedbackOverview: (lectureId?: string) =>
    request<FeedbackOverview>(
      `/api/feedback/overview${lectureId ? `?lecture_id=${lectureId}` : ''}`
    ),

  /** Get per-topic breakdown (all lectures, or one if lectureId given) */
  getFeedbackTopics: (lectureId?: string) =>
    request<FeedbackTopic[]>(
      `/api/feedback/topics${lectureId ? `?lecture_id=${lectureId}` : ''}`
    ),

  // ── Rating analytics (teacher) ──────────────────────────────────────────

  /** Get rating distribution analytics for one lecture (teacher) */
  getLectureRatingAnalytics: (lectureId: string) =>
    request<RatingAnalytics>(`/api/feedback/lectures/${lectureId}/ratings/analytics`),

  /** Get written reviews for one lecture (teacher, anonymized) */
  getLectureWrittenReviews: (lectureId: string) =>
    request<WrittenReview[]>(`/api/feedback/lectures/${lectureId}/ratings/reviews`),

  // ── Student rating endpoints ────────────────────────────────────────────

  /** Get the authenticated user's own rating for a lecture (null if none) */
  getMyRating: (lectureId: string) =>
    request<RatingRead | null>(`/api/feedback/lectures/${lectureId}/rating`),

  /** Create the student's rating (upserts if exists) */
  createRating: (lectureId: string, payload: RatingCreate) =>
    request<RatingRead>(`/api/feedback/lectures/${lectureId}/rating`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Update the student's existing rating */
  updateRating: (lectureId: string, payload: RatingCreate) =>
    request<RatingRead>(`/api/feedback/lectures/${lectureId}/rating`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  // ── Lecture Engagement (teacher) ───────────────────────────────────────

  /** Get aggregated video playback engagement stats (all or one lecture) */
  getLectureEngagement: (lectureId?: string) =>
    request<LectureEngagementStats>(
      `/api/feedback/engagement${lectureId ? `?lecture_id=${lectureId}` : ''}`
    ),

  // ── Problem Solving (teacher) ──────────────────────────────────────────

  /** Get doubt/problem-solving analytics (all or one lecture) */
  getProblemSolving: (lectureId?: string) =>
    request<ProblemSolvingStats>(
      `/api/feedback/problem-solving${lectureId ? `?lecture_id=${lectureId}` : ''}`
    ),

  // ── Teacher Performance Score ──────────────────────────────────────────

  /** Get the teacher's calculated performance score (teacher-wide) */
  getTeacherScore: () =>
    request<TeacherPerformanceScore>('/api/feedback/teacher-score'),

  // ── Playback tracking (student) ────────────────────────────────────────

  /**
   * Flush batched video playback events to the backend.
   * Call on pause, seek, unload, and periodically (debounced — not on timeupdate).
   */
  flushPlayback: (lectureId: string, payload: PlaybackFlush) =>
    fetch(`${API_BASE}/api/feedback/lectures/${lectureId}/playback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
      keepalive: true,    // survives page unload
    }).then(() => undefined),
}

export default api
