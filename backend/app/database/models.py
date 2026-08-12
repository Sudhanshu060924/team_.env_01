import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    video_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["LectureEventModel"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    notes: Mapped[list["NoteModel"]] = relationship(
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lecture: Mapped["Lecture"] = relationship(back_populates="notes")

    __table_args__ = (
        Index("ix_notes_lecture_id", "lecture_id"),
    )
