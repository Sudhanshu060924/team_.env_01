import { Lecture, LectureCreate, LectureEvent } from '@/types/lecture'
import { ChatThreadRead, TeacherThreadRead, ChatMessageRead } from '@/types/chat'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

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

  // ── Student chat endpoints ──────────────────────────────────────────────

  /** Get the authenticated student's own thread for this lecture */
  getStudentChat: (lectureId: string) =>
    request<ChatThreadRead>(`/lectures/${lectureId}/chat`),

  /** Post a new student doubt message */
  postStudentMessage: (lectureId: string, content: string) =>
    request<ChatMessageRead>(`/lectures/${lectureId}/chat`, {
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
}

export default api
