# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Query

from backend.agents.policy_agent import answer_question

router = APIRouter()


@router.get("/query")
def query_policy(
    q: str = Query(..., description="Policy question (e.g. What are NAAQS standards?)")
):
    """Query the RAG policy knowledge base."""
    try:
        result = answer_question(q)
        return result
    except Exception as exc:
        return {
            "answer": "Policy service unavailable.",
            "error": str(exc),
            "sources": [],
        }
