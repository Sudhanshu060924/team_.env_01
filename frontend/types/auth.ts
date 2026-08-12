// Auth types shared across the frontend

export interface User {
  id: string
  name: string
  email: string
  role: 'student' | 'teacher'
  created_at: string
}

export interface SignupPayload {
  name: string
  email: string
  password: string
  role: 'student' | 'teacher'
}

export interface LoginPayload {
  email: string
  password: string
}
