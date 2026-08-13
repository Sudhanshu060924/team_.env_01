"""Pydantic schemas for the Teacher Feedback / Analytics feature + Lecture Ratings."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Existing engagement analytics schemas
# ---------------------------------------------------------------------------

class FeedbackOverview(BaseModel):
    """Aggregated overview statistics for a teacher (or filtered to one lecture)."""
    total_lectures: int
    total_students: int
    total_questions: int       # student AI-chat questions
    total_doubts: int          # student ↔ teacher doubt messages from students
    total_ai_questions: int    # same as total_questions (kept for clarity)
    most_asked_topic: Optional[str] = None
    # Rating summary — populated when ratings exist
    avg_rating: Optional[float] = None
    total_ratings: int = 0
    most_rated_lecture: Optional[str] = None
    lowest_rated_lecture: Optional[str] = None
    # Teacher performance score — populated by extended service
    teacher_score: Optional["TeacherPerformanceScore"] = None


class FeedbackTopic(BaseModel):
    """Per-topic breakdown row — extended with playback + doubt data."""
    topic: str
    question_count: int
    percentage: float
    lecture_id: Optional[str] = None
    lecture_title: Optional[str] = None
    # Extended fields (populated when playback data exists)
    replay_count:   int = 0
    rewind_count:   int = 0
    pause_count:    int = 0
    completion_pct: float = 0.0


class FeedbackTopicDetail(BaseModel):
    """Topic detail with associated student questions (content, no PII)."""
    topic: str
    questions: List[str]       # question text only, anonymized


# ---------------------------------------------------------------------------
# Lecture Rating schemas
# ---------------------------------------------------------------------------

class RatingCreate(BaseModel):
    rating: int
    feedback: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("feedback")
    @classmethod
    def trim_feedback(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class RatingRead(BaseModel):
    """A student's rating for one lecture — returned to the student."""
    id: str
    lecture_id: str
    student_id: str
    rating: int
    feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rating analytics schemas (teacher-facing, anonymized)
# ---------------------------------------------------------------------------

class RatingDistribution(BaseModel):
    """How many ratings at each star level."""
    five: int = 0
    four: int = 0
    three: int = 0
    two: int = 0
    one: int = 0


class RatingAnalytics(BaseModel):
    """Aggregated rating analytics for a lecture or all teacher lectures."""
    avg_rating: Optional[float] = None
    total_ratings: int = 0
    distribution: RatingDistribution = RatingDistribution()


class WrittenReview(BaseModel):
    """One written review as shown to the teacher (anonymized — no student name/id)."""
    rating: int
    feedback: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Problem Solving (Student ↔ Teacher doubts — separate from AI chat)
# ---------------------------------------------------------------------------

class ProblemSolvingStats(BaseModel):
    """Aggregated doubt/problem-solving analytics for a teacher."""
    total_doubts: int = 0
    answered_doubts: int = 0
    response_rate_pct: float = 0.0       # 0–100
    avg_response_time_minutes: Optional[float] = None
    resolved_pct: float = 0.0           # answered / total × 100


# ---------------------------------------------------------------------------
# Teacher Performance Score
# ---------------------------------------------------------------------------

class TeacherPerformanceScore(BaseModel):
    """
    Composite teacher performance score in the range [0, 5].

    Sub-scores are on the same 0–5 scale.
    None means not enough data to compute that sub-score yet.
    """
    overall:            Optional[float] = None   # final composite score
    overall_rating:     Optional[float] = None   # from lecture ratings
    problem_solving:    Optional[float] = None   # from doubts analytics
    student_engagement: Optional[float] = None   # from playback engagement
    lecture_completion: Optional[float] = None   # from playback completion
    ai_dependency:      Optional[float] = None   # combined signal


# Update FeedbackOverview forward ref
FeedbackOverview.model_rebuild()
