from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteRead(BaseModel):
    note_id: str
    lecture_id: str
    content: str
    language: str = "english"
    created_at: datetime

    model_config = {"from_attributes": True}
