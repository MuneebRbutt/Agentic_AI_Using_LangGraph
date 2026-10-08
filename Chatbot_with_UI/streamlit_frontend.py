import streamlit as st 
from langgraph_tool_backend import chatbot, retrieve_all_threads
from langchain_core.messages import AIMessage, HumanMessage
from chat_persistence import (
    conversation_title, initialize_history, new_conversation, select_conversation,
)

TOOL_LABELS = {
    'duckduckgo_search': 'DuckDuckGo search',
    'get_stock_price': 'Stock price lookup',
    'calculator': 'Calculator',
}


def tool_labels(tool_names):
    return ', '.join(TOOL_LABELS.get(name, name) for name in tool_names)



def load_conversation(thread_id):
    return chatbot.get_state(
        config={'configurable': {'thread_id': thread_id}}
    ).values.get('messages', [])


initialize_history(
    st.session_state, st.query_params, retrieve_all_threads, load_conversation,
)

st.sidebar.title("Langgraph Chatbot")   
if st.sidebar.button("New Chat"):
    new_conversation(st.session_state, st.query_params)

st.sidebar.header("My Conversations")

for thread_id in st.session_state['chat_threads']:
    title = st.session_state['chat_titles'].get(thread_id)
    if title is None:
        continue
    if st.sidebar.button(title, key=f"chat_{thread_id}"):
        select_conversation(
            st.session_state, st.query_params, thread_id, load_conversation,
        )

CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        if message['role'] == 'user':
            st.text(message['content'])
        else:
            if message.get('tools_used'):
                st.caption(f"Tools used: {tool_labels(message['tools_used'])}")
            st.markdown(message['content'])

user_input = st.chat_input('Type Here')

if user_input:
    is_first_message = len(st.session_state['message_history']) == 0

    if is_first_message:
        thread_id = st.session_state['thread_id']
        st.session_state['chat_titles'][thread_id] = conversation_title(user_input)
        if thread_id not in st.session_state['chat_threads']:
            st.session_state['chat_threads'].insert(0, thread_id)

    st.session_state['message_history'].append({'role':'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    # Node updates reveal tool calls before execution without displaying tool output.
    with st.chat_message('assistant'):
        tools_used = []
        ai_message = ''
        with st.status('Thinking...', expanded=False) as status:
            for update in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='updates',
            ):
                for node_name, node_update in update.items():
                    if not isinstance(node_update, dict):
                        continue
                    if node_name == 'tools':
                        status.update(label='Preparing answer...')
                    for message in node_update.get('messages', []):
                        if not isinstance(message, AIMessage):
                            continue
                        if message.tool_calls:
                            current_tools = [call['name'] for call in message.tool_calls]
                            for name in current_tools:
                                if name not in tools_used:
                                    tools_used.append(name)
                            status.update(label=f'Using {tool_labels(current_tools)}...')
                        else:
                            ai_message = message.content
            status.update(
                label=f'Tools used: {tool_labels(tools_used)}' if tools_used else 'Answer ready',
                state='complete',
            )
        st.markdown(ai_message)
        
    st.session_state['message_history'].append({
        'role': 'assistant', 'content': ai_message, 'tools_used': tools_used,
    })
    if is_first_message:
        st.rerun()
        
        
