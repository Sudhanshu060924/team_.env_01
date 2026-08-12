export interface WSEventPayload {
  event_id: string
  lecture_id: string
  timestamp: number
  type: string
  source: string
  content: string
  metadata: Record<string, unknown>
}
