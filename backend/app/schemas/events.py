from typing import Any, Dict

from pydantic import BaseModel, Field


class LectureEvent(BaseModel):
    event_id: str
    lecture_id: str
    timestamp: float
    type: str
    source: str
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LectureEventRead(LectureEvent):
    """Same shape as LectureEvent; used for responses to distinguish create vs read."""
    model_config = {"from_attributes": True}
