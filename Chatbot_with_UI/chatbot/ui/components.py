"""Rendering and input handlers for the styled chatbot interface."""

import streamlit as st

from chatbot.config import STYLESHEET_PATH
from chatbot.conversations import conversation_title
from chatbot.service import ChatService
from chatbot.ui.state import reset_chat, select_conversation


SUGGESTIONS = (
    ("✦  Explain a concept", "Explain a concept in simple terms, with an example."),
    ("⌘  Write some code", "Help me write a small Python function."),
    ("◷  Plan my day", "Help me make a focused plan for my day."),
    ("▤  Summarize text", "Help me summarize a piece of text."),
)


def render_css() -> None:
    """Load the local stylesheet and inject it through Streamlit markdown."""
    css = STYLESHEET_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def render_sidebar(service: ChatService) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand-lockup">
                <div class="brand-mark">✦</div>
                <div>
                    <div class="brand-name">LangGraph Chatbot</div>
                    <div class="brand-tagline">A little clarity, one chat at a time</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("＋   New chat", key="new_chat", type="primary", use_container_width=True):
            reset_chat()
            st.rerun()

        st.markdown('<div class="section-label">YOUR CONVERSATIONS</div>', unsafe_allow_html=True)
        with st.container(key="conversation-list"):
            for thread_id in st.session_state["chat_threads"]:
                title = st.session_state["chat_titles"].get(thread_id)
                # Empty threads remain available through New chat, not in this list.
                if title is None:
                    continue

                active = thread_id == st.session_state["thread_id"]
                label = f"▤   {title}"
                if st.button(
                    label,
                    key=f"chat_{thread_id}",
                    type="primary" if active else "secondary",
                    use_container_width=True,
                    help=title,
                ):
                    select_conversation(thread_id, service)
                    st.rerun()

        st.markdown(
            """
            <div class="sidebar-footer">
                <span class="online-dot"></span>
                <span>LangGraph · OpenAI</span>
                <span class="online-label">ONLINE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_welcome() -> None:
    st.markdown(
        """
        <div class="welcome-wrap">
            <div class="welcome-orb">✦</div>
            <div class="eyebrow">YOUR AI COMPANION</div>
            <h1 class="welcome-title">How can I help you <span>today?</span></h1>
            <p class="welcome-subtitle">Ask a question, explore an idea, or make something useful.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="medium")
    for column, pair in zip((left, right), (SUGGESTIONS[:2], SUGGESTIONS[2:])):
        with column:
            for label, prompt in pair:
                if st.button(label, key=f"suggestion-{label}", use_container_width=True):
                    st.session_state["pending_prompt"] = prompt
                    st.rerun()


def render_messages() -> None:
    for message in st.session_state["message_history"]:
        is_user = message["role"] == "user"
        with st.chat_message(
            message["role"],
            avatar="🧑" if is_user else "✨",
        ):
            st.markdown(message["content"])


def handle_user_input(service: ChatService) -> None:
    user_input = st.chat_input("Message LangGraph Chatbot...")
    suggested_prompt = st.session_state.pop("pending_prompt", None)
    user_input = suggested_prompt or user_input
    if not user_input:
        return

    is_first_message = len(st.session_state["message_history"]) == 0
    thread_id = st.session_state["thread_id"]

    if is_first_message:
        st.session_state["chat_titles"][thread_id] = conversation_title(user_input)

    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="✨"):
        st.markdown(
            '<div class="typing-indicator"><span></span><span></span><span></span></div>',
            unsafe_allow_html=True,
        )
        ai_message = st.write_stream(service.stream_response(thread_id, user_input))

    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message}
    )

    # Refresh the sidebar to show the new title on a conversation's first turn.
    if is_first_message:
        st.rerun()
