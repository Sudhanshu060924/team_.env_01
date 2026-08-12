export interface Lecture {
  lecture_id: string
  title: string
  video_name: string
  status: 'live' | 'completed' | string
  created_at?: string
  completed_at?: string | null
}

export interface LectureCreate {
  title: string
  video_name: string
}

export interface LectureEvent {
  event_id: string
  lecture_id: string
  timestamp: number
  type: string
  source: string
  content: string
  metadata: Record<string, unknown>
}

export type LectureStatus = 'idle' | 'starting' | 'live' | 'completed' | 'error' | string
