"""Compatibility exports for the original persistent tutorial backend.

New code should use chatbot.service.create_sqlite_service for explicit ownership.
"""

import atexit

from chatbot.config import DATABASE_PATH as DATABASE_PATH
from chatbot.service import create_sqlite_service

_service = create_sqlite_service()
atexit.register(_service.close)
chatbot = _service.graph
checkpointer = _service.checkpointer
conn = _service.connection


def retrieve_all_threads() -> list[str]:
    """Return saved thread IDs in newest-first checkpoint order."""
    return _service.list_threads()
