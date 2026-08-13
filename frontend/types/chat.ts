// Types for the Student ↔ Teacher live doubt/chat feature

export interface ChatMessageRead {
  id: string
  thread_id: string
  sender_id: string
  sender_role: 'student' | 'teacher' | 'ai'
  content: string
  created_at: string
  // Phase 9 — AI chatbot fields (only present on AI reply messages)
  detected_topic?: string | null
  ai_answer?: string | null
}

export interface ChatThreadRead {
  thread_id: string
  lecture_id: string
  student_id: string
  created_at: string
  updated_at: string
  messages: ChatMessageRead[]
}

export interface StudentInfo {
  id: string
  name: string
}

export interface TeacherThreadRead {
  thread_id: string
  lecture_id: string
  student: StudentInfo
  messages: ChatMessageRead[]
}

// WebSocket message types for chat
export interface WSChatMessageCreated {
  type: 'chat_message_created'
  message: ChatMessageRead
}

// Phase 9 — AI chatbot response
export interface AIChatResponse {
  student_message: ChatMessageRead
  ai_message: ChatMessageRead
}

// Phase 9 — Teacher analytics
export interface TopicAnalytic {
  topic: string
  students_count: number
  percentage: number
  question_count: number
}

export interface LectureDoubtAnalytics {
  lecture_id: string
  total_students: number
  students_with_doubts: number
  total_questions: number
  most_asked_topic: string | null
  topics: TopicAnalytic[]
}
