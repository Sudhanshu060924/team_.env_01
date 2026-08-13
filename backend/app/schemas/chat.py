"""Pydantic schemas for the Student ↔ Teacher live doubt/chat feature + Phase 9 AI chatbot."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


MAX_MESSAGE_LENGTH = 2000


class ChatMessageCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message content must not be empty")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message must be at most {MAX_MESSAGE_LENGTH} characters")
        return v


class ChatMessageRead(BaseModel):
    id: str
    thread_id: str
    sender_id: str
    sender_role: str  # "student" | "teacher" | "ai"
    content: str
    created_at: datetime
    # Phase 9 — only present on AI reply messages
    detected_topic: Optional[str] = None
    ai_answer: Optional[str] = None

    model_config = {"from_attributes": True}


class StudentInfo(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class ChatThreadRead(BaseModel):
    """Student's own thread — returned by the student chat endpoint."""
    thread_id: str
    lecture_id: str
    student_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageRead]

    model_config = {"from_attributes": True}


class TeacherThreadRead(BaseModel):
    """One thread as seen by a teacher — includes student info."""
    thread_id: str
    lecture_id: str
    student: StudentInfo
    messages: List[ChatMessageRead]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Phase 9 — AI chatbot response
# ---------------------------------------------------------------------------

class AIChatResponse(BaseModel):
    """Returned when a student submits a chatbot question."""
    student_message: ChatMessageRead
    ai_message: ChatMessageRead


# ---------------------------------------------------------------------------
# Phase 9 — Teacher analytics
# ---------------------------------------------------------------------------

class TopicAnalytic(BaseModel):
    topic: str
    students_count: int
    percentage: float
    question_count: int


class LectureDoubtAnalytics(BaseModel):
    lecture_id: str
    total_students: int          # students who have access (student-visible lectures count)
    students_with_doubts: int
    total_questions: int
    most_asked_topic: Optional[str] = None
    topics: List[TopicAnalytic]
