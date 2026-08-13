// Types for the Teacher Feedback / Analytics feature + Lecture Ratings

// ---------------------------------------------------------------------------
// Teacher Performance Score
// ---------------------------------------------------------------------------

export interface TeacherPerformanceScore {
  overall: number | null
  overall_rating: number | null
  problem_solving: number | null
  student_engagement: number | null
  lecture_completion: number | null
  ai_dependency: number | null
}

// ---------------------------------------------------------------------------
// Feedback Overview
// ---------------------------------------------------------------------------

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
  // Teacher performance score
  teacher_score: TeacherPerformanceScore | null
}

// ---------------------------------------------------------------------------
// Topic Analytics (extended with playback data)
// ---------------------------------------------------------------------------

export interface FeedbackTopic {
  topic: string
  question_count: number
  percentage: number
  lecture_id?: string | null
  lecture_title?: string | null
  // Playback data per lecture
  replay_count: number
  rewind_count: number
  pause_count: number
  completion_pct: number
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

// ---------------------------------------------------------------------------
// Lecture Engagement (Playback Analytics — teacher view)
// ---------------------------------------------------------------------------

export interface RevisitSegment {
  start: number
  end: number
  event_type: string
  count: number
  label: string
}

export interface LectureEngagementStats {
  total_views: number
  avg_watch_seconds: number
  avg_completion_pct: number
  play_count: number
  pause_count: number
  rewind_count: number
  forward_count: number
  replay_count: number
  seek_count: number
  revisit_segments: RevisitSegment[]
}

// ---------------------------------------------------------------------------
// Problem Solving
// ---------------------------------------------------------------------------

export interface ProblemSolvingStats {
  total_doubts: number
  answered_doubts: number
  response_rate_pct: number
  avg_response_time_minutes: number | null
  resolved_pct: number
}

// ---------------------------------------------------------------------------
// Playback flush (student → backend)
// ---------------------------------------------------------------------------

export interface PlaybackSegmentItem {
  start: number
  end: number
  event_type: string
  count: number
}

export interface PlaybackFlush {
  play_count: number
  pause_count: number
  rewind_count: number
  forward_count: number
  replay_count: number
  seek_count: number
  watch_seconds: number
  completion_pct: number
  revisit_segments: PlaybackSegmentItem[]
}
