import pytest

from backend.agents.orchestrator import resolve_followup_context
from backend.services.conversation_memory import SessionMemoryManager


class FakeClassifier:
    pass


def make_memory(previous_question, session_id="followup-test"):
    memory = SessionMemoryManager()
    memory.add_turn(
        previous_question,
        "Previous assistant response",
        location="Pune",
        session_id=session_id,
    )
    return memory.get_session(session_id)


@pytest.mark.parametrize(
    ("previous", "followup", "expected"),
    [
        ("Forecast PM2.5 in Pune", "What about tomorrow?", "forecast"),
        ("Forecast PM2.5 in Pune", "Explain that forecast", "forecast"),
        ("What are CPCB NAAQS limits?", "What about tomorrow?", "policy_rag"),
    ],
)
def test_clear_followup_uses_previous_task(previous, followup, expected):
    memory = make_memory(previous)
    result = resolve_followup_context(followup, memory, ["Pune"])
    assert result is not None
    assert result["intent"] == expected
    assert previous in result["contextual_question"]
    assert followup in result["contextual_question"]


def test_unrelated_question_does_not_inherit_previous_task():
    memory = make_memory("Forecast PM2.5 in Pune")
    assert resolve_followup_context("Show pollution hotspots in Mumbai", memory, []) is None


def test_followup_without_history_does_not_invent_context():
    memory = SessionMemoryManager().get_session("empty-followup")
    assert resolve_followup_context("What about tomorrow?", memory, []) is None


def test_context_is_limited_to_its_own_session():
    manager = SessionMemoryManager()
    manager.add_turn("Forecast PM2.5 in Pune", "Forecast answer", "Pune", "session-a")
    session_b = manager.get_session("session-b")
    assert resolve_followup_context("What about tomorrow?", session_b, []) is None
