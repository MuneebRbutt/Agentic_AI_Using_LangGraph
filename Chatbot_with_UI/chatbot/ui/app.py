"""Compose the persistent Streamlit application."""

import streamlit as st

from chatbot.ui.components import (
    handle_user_input,
    render_css,
    render_messages,
    render_sidebar,
    render_welcome,
)
from chatbot.ui.resources import get_chat_service
from chatbot.ui.state import initialize_state


def main() -> None:
    """Configure the page and render one Streamlit script run."""
    st.set_page_config(
        page_title="LangGraph Chatbot",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    service = get_chat_service()
    initialize_state(service)
    render_css()
    render_sidebar(service)

    if st.session_state["message_history"]:
        render_messages()
    else:
        render_welcome()

    handle_user_input(service)
