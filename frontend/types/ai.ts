import { Lecture, LectureEvent } from './lecture'

// ── WebSocket message types (server → client) ─────────────────────────────

export interface WSMessage {
  type: string
  lecture_id?: string
  timestamp?: number
  content?: string
  message?: string
  metadata?: Record<string, unknown>
}

export interface WSConnectedMessage extends WSMessage {
  type: 'connected'
  lecture_id: string
  message: string
}

export interface WSTranslationMessage extends WSMessage {
  type: 'translation'
  lecture_id: string
  timestamp: number
  content: string
  metadata: { language: string }
}

export interface WSTopicUpdateMessage extends WSMessage {
  type: 'topic_update'
  lecture_id: string
  timestamp: number
  content: string
  metadata: { subtopic?: string }
}

export interface WSImportantEventMessage extends WSMessage {
  type: 'important_event'
  lecture_id: string
  timestamp: number
  content: string
}

export interface WSNotesMessage extends WSMessage {
  type: 'notes'
  lecture_id: string
  content: string
}

export interface WSAnswerMessage extends WSMessage {
  type: 'answer'
  lecture_id: string
  content: string
}

export interface WSErrorMessage extends WSMessage {
  type: 'error'
  message: string
}

// ── AI result types (accumulated in UI state) ──────────────────────────────

export interface AIResult {
  type: string
  lecture_id: string
  timestamp?: number
  content?: string
  metadata?: Record<string, unknown>
}

export interface Translation {
  timestamp: number
  original: string
  translated: string
  language: string
}

export interface TopicState {
  topic: string
  subtopic: string
  timestamp: number
}

export interface ImportantEvent {
  id: string
  timestamp: number
  content: string
  isFormula: boolean
}

export interface ChatMessage {
  id: string
  role: 'student' | 'ai'
  content: string
  timestamp: number
}
