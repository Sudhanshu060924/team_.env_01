// Types for the Student ↔ Teacher live doubt/chat feature

export interface ChatMessageRead {
  id: string
  thread_id: string
  sender_id: string
  sender_role: 'student' | 'teacher'
  content: string
  created_at: string
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
