"""Presentation layer for the persistent LangGraph chatbot."""

from pathlib import Path
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph_database_backend import chatbot, retrieve_all_threads


SUGGESTIONS = (
    ("✦  Explain a concept", "Explain a concept in simple terms, with an example."),
    ("⌘  Write some code", "Help me write a small Python function."),
    ("◷  Plan my day", "Help me make a focused plan for my day."),
    ("▤  Summarize text", "Help me summarize a piece of text."),
)

st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def generate_thread_id():
    return str(uuid.uuid4())


def conversation_title(text):
    title = " ".join(text.split())
    return title[:40] + ("..." if len(title) > 40 else "") or "New Chat"


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id):
    """Read the saved messages for one existing checkpoint thread."""
    return chatbot.get_state(
        config={"configurable": {"thread_id": thread_id}}
    ).values.get("messages", [])


def select_conversation(thread_id):
    """Keep the existing URL selection and checkpoint thread behavior."""
    st.session_state["thread_id"] = thread_id
    st.query_params["thread_id"] = thread_id
    st.session_state["message_history"] = [
        {
            "role": "user" if isinstance(message, HumanMessage) else "assistant",
            "content": message.content,
        }
        for message in load_conversation(thread_id)
    ]


def reset_chat():
    # Reuse an untouched empty thread; create a new one after a conversation.
    if st.session_state["message_history"]:
        thread_id = generate_thread_id()
    else:
        thread_id = st.session_state["thread_id"]

    st.session_state["thread_id"] = thread_id
    st.session_state["message_history"] = []
    st.query_params["thread_id"] = thread_id
    add_thread(thread_id)


def initialize_state():
    if "chat_threads" not in st.session_state:
        st.session_state["chat_threads"] = retrieve_all_threads()

    # Titles are presentation data, so rebuild them from persisted user messages
    # when Streamlit starts a fresh browser session.
    if "chat_titles" not in st.session_state:
        st.session_state["chat_titles"] = {}
        for thread_id in st.session_state["chat_threads"]:
            for message in load_conversation(thread_id):
                if isinstance(message, HumanMessage):
                    st.session_state["chat_titles"][thread_id] = conversation_title(
                        message.content
                    )
                    break

    if "thread_id" not in st.session_state:
        requested_thread = st.query_params.get("thread_id")
        if requested_thread not in st.session_state["chat_threads"]:
            # An empty chat has no checkpoint yet; its UUID is still in the URL.
            try:
                requested_thread = str(uuid.UUID(requested_thread))
            except (ValueError, TypeError, AttributeError):
                requested_thread = next(
                    iter(st.session_state["chat_titles"]), generate_thread_id()
                )
        st.session_state["thread_id"] = requested_thread

    add_thread(st.session_state["thread_id"])
    if "message_history" not in st.session_state:
        select_conversation(st.session_state["thread_id"])


def render_css():
    """Load the local stylesheet and inject it through Streamlit markdown."""
    css_path = Path(__file__).with_name("style.css")
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def render_sidebar():
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
                    select_conversation(thread_id)
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


def render_welcome():
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


def render_messages():
    for message in st.session_state["message_history"]:
        is_user = message["role"] == "user"
        with st.chat_message(
            message["role"],
            avatar="🧑" if is_user else "✨",
        ):
            st.markdown(message["content"])


def handle_user_input():
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

    # Keep the graph invocation, input shape, thread ID, and stream mode intact.
    config = {"configurable": {"thread_id": thread_id}}

    def response_tokens():
        for message_chunk, metadata in chatbot.stream(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
            stream_mode="messages",
        ):
            if message_chunk.content:
                yield message_chunk.content

    with st.chat_message("assistant", avatar="✨"):
        st.markdown(
            '<div class="typing-indicator"><span></span><span></span><span></span></div>',
            unsafe_allow_html=True,
        )
        ai_message = st.write_stream(response_tokens())

    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message}
    )

    # Refresh the sidebar to show the new title on a conversation's first turn.
    if is_first_message:
        st.rerun()


def main():
    initialize_state()
    render_css()
    render_sidebar()

    if st.session_state["message_history"]:
        render_messages()
    else:
        render_welcome()

    handle_user_input()


if __name__ == "__main__":
    main()
