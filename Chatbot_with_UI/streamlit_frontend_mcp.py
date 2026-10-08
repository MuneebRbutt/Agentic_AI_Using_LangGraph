import queue

import streamlit as st
from langgraph_mcp_backend import chatbot, retrieve_all_threads, submit_async_task, run_async
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from chat_persistence import (
    conversation_title, initialize_history, new_conversation, select_conversation,
)

def load_conversation(thread_id):
    state = run_async(chatbot.aget_state(
        config={"configurable": {"thread_id": thread_id}}
    ))
    return state.values.get("messages", [])


initialize_history(
    st.session_state, st.query_params, retrieve_all_threads, load_conversation,
)

st.sidebar.title("LangGraph MCP Chatbot")
if st.sidebar.button("New Chat"):
    new_conversation(st.session_state, st.query_params)

st.sidebar.header("My Conversations")
for thread_id in st.session_state["chat_threads"]:
    title = st.session_state["chat_titles"].get(thread_id)
    if title is None:
        continue
    if st.sidebar.button(title, key=f"chat_{thread_id}"):
        select_conversation(
            st.session_state, st.query_params, thread_id, load_conversation,
        )

# ============================ Main UI ============================

# Render history
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.text(message["content"])

user_input = st.chat_input("Type here")

if user_input:
    is_first_message = not st.session_state["message_history"]
    if is_first_message:
        thread_id = st.session_state["thread_id"]
        st.session_state["chat_titles"][thread_id] = conversation_title(user_input)
        if thread_id not in st.session_state["chat_threads"]:
            st.session_state["chat_threads"].insert(0, thread_id)

    # Show user's message
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    CONFIG = {
        "configurable": {"thread_id": st.session_state["thread_id"]},
        "metadata": {"thread_id": st.session_state["thread_id"]},
        "run_name": "chat_turn",
    }

    # Assistant streaming block
    with st.chat_message("assistant"):
        # Use a mutable holder so the generator can set/modify it
        status_holder = {"box": None}

        def ai_only_stream():
            event_queue: queue.Queue = queue.Queue()

            async def run_stream():
                try:
                    async for message_chunk, metadata in chatbot.astream(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=CONFIG,
                        stream_mode="messages",
                    ):
                        event_queue.put((message_chunk, metadata))
                except Exception as exc:
                    event_queue.put(("error", exc))
                finally:
                    event_queue.put(None)

            submit_async_task(run_stream())

            while True:
                item = event_queue.get()
                if item is None:
                    break
                message_chunk, metadata = item
                if message_chunk == "error":
                    raise metadata

                # Lazily create & update the SAME status container when any tool runs
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )

                # Stream ONLY assistant tokens
                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

        # Finalize only if a tool was actually used
        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    # Save assistant message
    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message}
    )
    if is_first_message:
        st.rerun()
