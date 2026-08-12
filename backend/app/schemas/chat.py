"""Pydantic schemas for the Student ↔ Teacher live doubt/chat feature."""
from datetime import datetime
from typing import List

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
    sender_role: str  # "student" | "teacher"
    content: str
    created_at: datetime

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
