from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LectureCreate(BaseModel):
    title: str
    video_name: str


class LectureRead(BaseModel):
    lecture_id: str
    title: str
    video_name: str
    status: str
    teacher_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    video_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None

    model_config = {"from_attributes": True}
