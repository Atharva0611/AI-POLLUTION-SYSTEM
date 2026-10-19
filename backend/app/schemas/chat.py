from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    status: str = "ok"
    intent: Optional[str] = None
    location: Optional[str] = None
