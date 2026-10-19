from uuid import uuid4

from backend.agents.orchestrator import run_pipeline


def process_chat(message: str, session_id: str | None = None) -> dict:
    question = (message or "").strip()
    sid = session_id or str(uuid4())

    if not question:
        return {
            "answer": "Please enter a question.",
            "session_id": sid,
            "status": "invalid",
        }

    try:
        result = run_pipeline({
            "question": question,
            "session_id": sid,
        })

        answer = (
            result.get("final_answer")
            or result.get("direct_message")
            or result.get("error")
        )

        if not answer:
            answer = (
                "I couldn't generate a reliable answer. "
                "Please try rephrasing your question."
            )

        return {
            "answer": str(answer),
            "session_id": sid,
            "status": "ok" if result.get("final_answer") or result.get("direct_message") else "partial",
            "intent": result.get("intent"),
            "location": result.get("location"),
        }
    except Exception:
        # Avoid leaking API keys, internal paths, or stack traces to chat users.
        return {
            "answer": (
                "I couldn't complete that request because an internal service "
                "encountered an error. Please try again."
            ),
            "session_id": sid,
            "status": "error",
        }
