from datetime import datetime

from pydantic import BaseModel


class NoteRead(BaseModel):
    note_id: str
    lecture_id: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
