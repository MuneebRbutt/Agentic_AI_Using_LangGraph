"""Conversation selection and history for a Streamlit browser session."""

from uuid import UUID

import streamlit as st
from langchain_core.messages import HumanMessage

from chatbot.conversations import conversation_title, generate_thread_id
from chatbot.service import ChatService


def add_thread(thread_id: str) -> None:
    """Register a conversation once in the current session."""
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def select_conversation(
    thread_id: str, service: ChatService, *, sync_url: bool = True
) -> None:
    """Select a checkpoint thread and restore its display history."""
    st.session_state["thread_id"] = thread_id
    if sync_url:
        st.query_params["thread_id"] = thread_id
    st.session_state["message_history"] = [
        {
            "role": "user" if isinstance(message, HumanMessage) else "assistant",
            "content": message.content,
        }
        for message in service.load_messages(thread_id)
    ]


def reset_chat(*, sync_url: bool = True) -> None:
    """Start a conversation, reusing the current thread while it is empty."""
    thread_id = (
        generate_thread_id()
        if st.session_state["message_history"]
        else st.session_state["thread_id"]
    )
    st.session_state["thread_id"] = thread_id
    st.session_state["message_history"] = []
    if sync_url:
        st.query_params["thread_id"] = thread_id
    add_thread(thread_id)


def initialize_state(service: ChatService, *, persistent: bool = True) -> None:
    """Restore saved conversations or initialize an isolated in-memory session."""
    if "chat_threads" not in st.session_state:
        st.session_state["chat_threads"] = service.list_threads() if persistent else []

    if "chat_titles" not in st.session_state:
        st.session_state["chat_titles"] = {}
        for thread_id in st.session_state["chat_threads"]:
            for message in service.load_messages(thread_id):
                if isinstance(message, HumanMessage):
                    st.session_state["chat_titles"][thread_id] = conversation_title(
                        message.text
                    )
                    break

    if "thread_id" not in st.session_state:
        requested_thread = st.query_params.get("thread_id") if persistent else None
        if requested_thread not in st.session_state["chat_threads"]:
            # An empty conversation has no checkpoint yet; retain its URL UUID.
            try:
                requested_thread = str(UUID(requested_thread))
            except (ValueError, TypeError, AttributeError):
                requested_thread = next(
                    iter(st.session_state["chat_titles"]), generate_thread_id()
                )
        st.session_state["thread_id"] = requested_thread

    add_thread(st.session_state["thread_id"])
    if "message_history" not in st.session_state:
        select_conversation(
            st.session_state["thread_id"], service, sync_url=persistent
        )
