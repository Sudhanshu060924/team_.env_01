// Types for the Teacher Feedback / Analytics feature + Lecture Ratings

export interface FeedbackOverview {
  total_lectures: number
  total_students: number
  total_questions: number
  total_doubts: number
  total_ai_questions: number
  most_asked_topic: string | null
  // Rating fields
  avg_rating: number | null
  total_ratings: number
  most_rated_lecture: string | null
  lowest_rated_lecture: string | null
}

export interface FeedbackTopic {
  topic: string
  question_count: number
  percentage: number
  lecture_id?: string | null
  lecture_title?: string | null
}

// ---------------------------------------------------------------------------
// Lecture Ratings
// ---------------------------------------------------------------------------

export interface RatingCreate {
  rating: number
  feedback?: string | null
}

export interface RatingRead {
  id: string
  lecture_id: string
  student_id: string
  rating: number
  feedback: string | null
  created_at: string
  updated_at: string
}

// Teacher analytics

export interface RatingDistribution {
  five: number
  four: number
  three: number
  two: number
  one: number
}

export interface RatingAnalytics {
  avg_rating: number | null
  total_ratings: number
  distribution: RatingDistribution
}

export interface WrittenReview {
  rating: number
  feedback: string
  created_at: string
}
