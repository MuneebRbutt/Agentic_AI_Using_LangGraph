import streamlit as st 
from langgraph_tool_backend import chatbot
from langchain_core.messages import AIMessage, HumanMessage
import uuid # Importing this to generate dynamic threadids rather than hardcoating it for each conversation.

TOOL_LABELS = {
    'duckduckgo_search': 'DuckDuckGo search',
    'get_stock_price': 'Stock price lookup',
    'calculator': 'Calculator',
}


def tool_labels(tool_names):
    return ', '.join(TOOL_LABELS.get(name, name) for name in tool_names)



# Utility Functions
def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id

# Function to start a new chat
def reset_chat():
    # Do not create another empty thread when the current chat has no messages.
    # This prevents multiple "New Chat" entries in the sidebar.
    if st.session_state['message_history']:
        thread_id = generate_thread_id()
    else:
        thread_id = st.session_state['thread_id']

    st.session_state['thread_id'] = thread_id
    add_thread(thread_id)
    st.session_state['message_history'] = []
    
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

    if thread_id not in st.session_state['chat_titles']:
        st.session_state['chat_titles'][thread_id] = "New Chat"


def remove_duplicate_new_chats():
    """Keep one placeholder chat and remove duplicates from older sessions."""
    placeholder_threads = [
        thread_id
        for thread_id in st.session_state['chat_threads']
        if st.session_state['chat_titles'].get(thread_id) == "New Chat"
    ]

    if len(placeholder_threads) <= 1:
        return

    # Prefer the currently selected placeholder; otherwise keep the first one.
    keep_thread = st.session_state['thread_id']
    if keep_thread not in placeholder_threads:
        keep_thread = placeholder_threads[0]

    st.session_state['chat_threads'] = [
        thread_id
        for thread_id in st.session_state['chat_threads']
        if thread_id not in placeholder_threads or thread_id == keep_thread
    ]
    for thread_id in placeholder_threads:
        if thread_id != keep_thread:
            st.session_state['chat_titles'].pop(thread_id, None)
        
# This function is loading conversations respectively.       
def load_conversation(thread_id):
    return chatbot.get_state(config={'configurable': {'thread_id': thread_id}}).values.get('messages', [])

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()
    
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []    

# implementing the logic for giving each chat a name.
if 'chat_titles' not in st.session_state:
    st.session_state['chat_titles'] = {}
    
add_thread(st.session_state['thread_id'])    
remove_duplicate_new_chats()
    
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []
    
    
    
st.sidebar.title("Langgraph Chatbot")   
if st.sidebar.button("New Chat"):
    reset_chat() 

st.sidebar.header("My Conversations")

for thread_id in st.session_state['chat_threads']:
    title = st.session_state['chat_titles'].get(thread_id, "New Chat")

    # Empty chats are available through the main New Chat button, so do not
    # list their placeholder title as a conversation.
    if title == "New Chat":
        continue

    if st.sidebar.button(title, key=f"chat_{thread_id}"):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)
        
        temp_messages = []
        tools_used = []
        for message in messages:
            if isinstance(message, HumanMessage):
                role = 'user'
                tools_used = []
            elif isinstance(message, AIMessage) and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call['name'] not in tools_used:
                        tools_used.append(tool_call['name'])
                continue
            elif isinstance(message, AIMessage) and not message.tool_calls:
                role = 'assistant'
            else:
                continue
            temp_messages.append({
                'role': role,
                'content': message.content,
                'tools_used': list(tools_used) if role == 'assistant' else [],
            })
        st.session_state['message_history'] = temp_messages            

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
        title = " ".join(user_input.split())
        title = title[:40] + ("..." if len(title) > 40 else "")

        st.session_state['chat_titles'][
            st.session_state['thread_id']
        ] = title or "New Chat"
    
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
        
        
