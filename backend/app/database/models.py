import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())




class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "student" | "teacher"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lectures: Mapped[list["Lecture"]] = relationship(
        back_populates="teacher", foreign_keys="[Lecture.teacher_id]"
    )
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="student", foreign_keys="[ChatThread.student_id]"
    )
    sent_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="sender", foreign_keys="[ChatMessage.sender_id]"
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    video_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="live")
    teacher_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Video storage — populated when a teacher uploads the lecture recording
    video_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cloudinary_public_id: Mapped[str | None] = mapped_column(String, nullable=True)

    teacher: Mapped["User | None"] = relationship(
        back_populates="lectures", foreign_keys=[teacher_id]
    )
    events: Mapped[list["LectureEventModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    notes: Mapped[list["NoteModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )


class LectureEventModel(Base):
    __tablename__ = "lecture_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(String, ForeignKey("lectures.id"), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lecture: Mapped["Lecture"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_lecture_events_lecture_id", "lecture_id"),
        Index("ix_lecture_events_timestamp", "timestamp"),
        Index("ix_lecture_events_type", "type"),
    )


class NoteModel(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(String, ForeignKey("lectures.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(
        String, default="english", server_default="english", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lecture: Mapped["Lecture"] = relationship(back_populates="notes")

    __table_args__ = (
        UniqueConstraint("lecture_id", "language", name="uk_notes_lecture_language"),
        Index("ix_notes_lecture_id", "lecture_id"),
    )


# ---------------------------------------------------------------------------
# Chat Models
# ---------------------------------------------------------------------------

class ChatThread(Base):
    """One thread per student per lecture — holds all doubt messages for that pair."""
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(
        String, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    lecture: Mapped["Lecture"] = relationship(back_populates="chat_threads")
    student: Mapped["User"] = relationship(
        back_populates="chat_threads", foreign_keys=[student_id]
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    __table_args__ = (
        UniqueConstraint("lecture_id", "student_id", name="uq_chat_thread_lecture_student"),
        Index("ix_chat_threads_lecture_id", "lecture_id"),
        Index("ix_chat_threads_student_id", "student_id"),
    )


class ChatMessage(Base):
    """A single message inside a ChatThread."""
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_role: Mapped[str] = mapped_column(String, nullable=False)  # "student" | "teacher"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    thread: Mapped["ChatThread"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(
        back_populates="sent_messages", foreign_keys=[sender_id]
    )

    __table_args__ = (
        Index("ix_chat_messages_thread_id", "thread_id"),
        Index("ix_chat_messages_created_at", "created_at"),
    )
