"""Cache backend resources across Streamlit script reruns."""

import atexit

import streamlit as st

from chatbot.service import ChatService, create_memory_service, create_sqlite_service


@st.cache_resource
def get_chat_service(*, persistent: bool = True) -> ChatService:
    """Create one backend per mode and close its resources at process exit."""
    service = create_sqlite_service() if persistent else create_memory_service()
    atexit.register(service.close)
    return service
