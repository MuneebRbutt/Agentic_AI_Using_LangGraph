"""Compatibility exports for the original in-memory tutorial backend.

New code should use chatbot.service.create_memory_service for explicit ownership.
"""

from chatbot.service import create_memory_service

_service = create_memory_service()
chatbot = _service.graph
checkpointer = _service.checkpointer
