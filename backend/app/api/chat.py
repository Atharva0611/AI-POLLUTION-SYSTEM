from fastapi import APIRouter
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.chat_service import process_chat

router = APIRouter()


@router.get("/health")
def chat_health():
    return {"status": "ok", "service": "oriva-chat"}


@router.post("", response_model=ChatResponse)
def send_chat_message(payload: ChatRequest):
    result = process_chat(payload.message, payload.session_id)
    return ChatResponse(**result)
