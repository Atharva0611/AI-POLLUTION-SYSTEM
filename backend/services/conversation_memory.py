"""
Session Conversation Memory Manager
====================================
Maintains lightweight session context for the terminal and agentic interfaces:
- Tracks recent user queries and assistant responses.
- Stores the last mentioned location and compared locations.
- Resolves context-dependent queries ("what about there?", "what about tomorrow?", "compare both").
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from threading import RLock


class ConversationMemory:
    """Thread-safe session memory for chatbot interactions."""

    def __init__(self, max_history: int = 15, default_location: str = "Pune"):
        self.max_history = max_history
        self.default_location = default_location
        self.history: List[Dict[str, str]] = []
        self.last_location: Optional[str] = None
        self.recent_locations: List[str] = []

    def add_turn(self, user_msg: str, assistant_msg: str, location: Optional[str] = None):
        """Record a conversation turn and update location memory."""
        self.history.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "user": user_msg,
            "assistant": assistant_msg,
            "location": location or self.last_location or self.default_location,
        })
        if location:
            loc_title = location.title()
            self.last_location = loc_title
            if loc_title in self.recent_locations:
                self.recent_locations.remove(loc_title)
            self.recent_locations.append(loc_title)
            # Keep up to 5 recent locations
            if len(self.recent_locations) > 5:
                self.recent_locations.pop(0)

        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_last_location(self) -> Optional[str]:
        """Return the most recent valid location, or None if none set yet."""
        return self.last_location

    def get_recent_locations(self) -> List[str]:
        """Return list of recently discussed locations for comparisons."""
        return list(self.recent_locations)

    def get_history(self) -> List[Dict[str, Any]]:
        """Return list of conversation turns in this session."""
        return list(self.history)

    def clear(self):
        """Reset conversation session history."""
        self.history.clear()
        self.last_location = None
        self.recent_locations = []

    def format_history(self) -> str:
        """Format history for the 'history' command."""
        if not self.history:
            return "No previous conversation history in this session."
        lines = ["CONVERSATION HISTORY", "=" * 60]
        for i, turn in enumerate(self.history, start=1):
            lines.append(f"[{turn['timestamp']}] Turn #{i}")
            lines.append(f"  User : {turn['user']}")
            # Truncate assistant answer if long
            ans_snippet = turn['assistant'].split("\n")[0][:80]
            lines.append(f"  AI   : {ans_snippet}...")
            lines.append("-" * 60)
        return "\n".join(lines)


class SessionMemoryManager:
    """Maintain independent conversation memory for each session ID.

    Calls without a session ID use a default session for terminal compatibility.
    """

    def __init__(self, max_history: int = 15, default_location: str = "Pune"):
        self.max_history = max_history
        self.default_location = default_location
        self._sessions = {}
        self._lock = RLock()
        self._default_session_id = "__oriva_default_terminal_session__"

    def get_session(self, session_id=None) -> ConversationMemory:
        key = str(session_id).strip() if session_id is not None else ""
        if not key:
            key = self._default_session_id

        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = ConversationMemory(
                    max_history=self.max_history,
                    default_location=self.default_location,
                )
            return self._sessions[key]

    def add_turn(self, user_msg, assistant_msg, location=None, session_id=None):
        self.get_session(session_id).add_turn(
            user_msg, assistant_msg, location=location
        )

    def get_last_location(self, session_id=None):
        return self.get_session(session_id).get_last_location()

    def get_recent_locations(self, session_id=None):
        return self.get_session(session_id).get_recent_locations()

    def get_history(self, session_id=None):
        return self.get_session(session_id).get_history()

    def clear(self, session_id=None):
        self.get_session(session_id).clear()

    def format_history(self, session_id=None):
        return self.get_session(session_id).format_history()


# Session-aware manager; no-ID calls preserve terminal compatibility.
SESSION_MEMORY = SessionMemoryManager()
