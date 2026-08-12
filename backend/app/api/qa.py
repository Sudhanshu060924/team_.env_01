from fastapi import APIRouter

router = APIRouter()


@router.post("/ask")
async def ask_question(payload: dict):
    """Stub: Phase 2 will route through the QA LangGraph."""
    return {"answer": "QA stub – Phase 2", "sources": []}
