from backend.services.conversation_memory import SessionMemoryManager


def test_locations_are_isolated_between_sessions():
    memory = SessionMemoryManager()

    memory.add_turn(
        "Current AQI in Pune?",
        "Pune report",
        location="Pune",
        session_id="session-pune",
    )
    memory.add_turn(
        "Current AQI in Mumbai?",
        "Mumbai report",
        location="Mumbai",
        session_id="session-mumbai",
    )

    assert memory.get_last_location("session-pune") == "Pune"
    assert memory.get_last_location("session-mumbai") == "Mumbai"
    assert memory.get_recent_locations("session-pune") == ["Pune"]
    assert memory.get_recent_locations("session-mumbai") == ["Mumbai"]


def test_history_is_isolated_between_sessions():
    memory = SessionMemoryManager()
    memory.add_turn("Question A", "Answer A", location="Pune", session_id="A")
    memory.add_turn("Question B", "Answer B", location="Delhi", session_id="B")

    assert len(memory.get_history("A")) == 1
    assert memory.get_history("A")[0]["user"] == "Question A"
    assert memory.get_history("B")[0]["user"] == "Question B"


def test_missing_session_id_uses_terminal_default():
    memory = SessionMemoryManager()
    memory.add_turn("Terminal question", "Terminal answer", location="Pune")

    assert memory.get_last_location() == "Pune"
    assert memory.get_history()[0]["user"] == "Terminal question"
    assert memory.get_last_location("web-session") is None


def test_clearing_one_session_does_not_clear_another():
    memory = SessionMemoryManager()
    memory.add_turn("A", "Answer A", location="Pune", session_id="A")
    memory.add_turn("B", "Answer B", location="Mumbai", session_id="B")

    memory.clear("A")

    assert memory.get_history("A") == []
    assert memory.get_last_location("A") is None
    assert memory.get_last_location("B") == "Mumbai"
