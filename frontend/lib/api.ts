import { Lecture, LectureCreate } from '@/types/lecture'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () =>
    request<{ status: string; service: string }>('/health'),

  startLecture: (payload: LectureCreate) =>
    request<Lecture>('/lectures/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getLecture: (lectureId: string) =>
    request<Lecture>(`/lectures/${lectureId}`),

  completeLecture: (lectureId: string) =>
    request<Lecture>(`/lectures/${lectureId}/complete`, { method: 'POST' }),

  getEvents: (lectureId: string, type?: string) =>
    request<unknown[]>(`/lectures/${lectureId}/events${type ? `?type=${type}` : ''}`),

  getNotes: (lectureId: string) =>
    request<unknown[]>(`/lectures/${lectureId}/notes`),

  askQuestion: (lectureId: string, question: string) =>
    request<{ answer: string; sources: string[] }>(
      `/lectures/${lectureId}/questions`,
      {
        method: 'POST',
        body: JSON.stringify({ question }),
      }
    ),
}

export default api
