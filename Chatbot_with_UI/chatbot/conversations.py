"""Small conversation helpers shared by both interfaces."""

from uuid import uuid4

TITLE_MAX_LENGTH = 40
DEFAULT_CHAT_TITLE = "New Chat"


def generate_thread_id() -> str:
    """Return a URL-safe identifier for a new conversation."""
    return str(uuid4())


def conversation_title(text: str) -> str:
    """Collapse whitespace and truncate a prompt for the conversation list."""
    title = " ".join(text.split())
    suffix = "..." if len(title) > TITLE_MAX_LENGTH else ""
    return title[:TITLE_MAX_LENGTH] + suffix or DEFAULT_CHAT_TITLE
