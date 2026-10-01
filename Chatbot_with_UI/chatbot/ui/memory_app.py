"""Simple Streamlit interface for the in-memory tutorial backend."""

import streamlit as st

from chatbot.conversations import conversation_title
from chatbot.service import ChatService
from chatbot.ui.resources import get_chat_service
from chatbot.ui.state import initialize_state, reset_chat, select_conversation


def render_sidebar(service: ChatService) -> None:
    st.sidebar.title("Langgraph Chatbot")
    if st.sidebar.button("New Chat"):
        reset_chat(sync_url=False)

    st.sidebar.header("My Conversations")
    for thread_id in st.session_state["chat_threads"]:
        title = st.session_state["chat_titles"].get(thread_id)
        if title is None:
            continue
        if st.sidebar.button(title, key=f"chat_{thread_id}"):
            select_conversation(thread_id, service, sync_url=False)


def render_messages() -> None:
    for message in st.session_state["message_history"]:
        with st.chat_message(message["role"]):
            st.text(message["content"])


def handle_user_input(service: ChatService) -> None:
    user_input = st.chat_input("Type Here")
    if not user_input:
        return

    is_first_message = not st.session_state["message_history"]
    thread_id = st.session_state["thread_id"]
    if is_first_message:
        st.session_state["chat_titles"][thread_id] = conversation_title(user_input)

    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_text = ""
        for token in service.stream_response(thread_id, user_input):
            response_text += token
            response_placeholder.markdown(response_text)

    st.session_state["message_history"].append(
        {"role": "assistant", "content": response_text}
    )
    if is_first_message:
        st.rerun()


def main() -> None:
    """Render the original minimal interface with shared conversation logic."""
    service = get_chat_service(persistent=False)
    initialize_state(service, persistent=False)
    render_sidebar(service)
    render_messages()
    handle_user_input(service)
