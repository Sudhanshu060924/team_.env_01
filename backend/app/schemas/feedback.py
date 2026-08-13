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


class FeedbackTopic(BaseModel):
    """Per-topic breakdown row."""
    topic: str
    question_count: int
    percentage: float
    lecture_id: Optional[str] = None
    lecture_title: Optional[str] = None


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
