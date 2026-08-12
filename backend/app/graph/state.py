"""LangGraph shared state definitions — Phase 2."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class GraphState(BaseModel):
    lecture_id: str = ""
    transcript: str = ""
    translation: str = ""
    topic: str = ""
    notes: List[str] = []
    qa_answer: str = ""
    metadata: Dict[str, Any] = {}
