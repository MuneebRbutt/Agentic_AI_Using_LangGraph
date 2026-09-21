import streamlit as st 
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage
import uuid # Importing this to generate dynamic threadids rather than hardcoating it for each conversation.



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
        for message in messages:
            if isinstance(message, HumanMessage):
                role = 'user'
            else:
                role = 'assistant'
            temp_messages.append({'role':role, 'content':message.content})
        st.session_state['message_history'] = temp_messages            

CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

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
     
    
    # response = chatbot.invoke({'messages': [HumanMessage(content=user_input)]}, config=CONFIG) 
    # ai_message = response['messages'][-1].content 
                    
    with st.chat_message('assistant'):
        response_placeholder = st.empty()
        response_text = ""
        for message_chunk, metadata in chatbot.stream(
            {'messages': [HumanMessage(content=user_input)]},
            config=CONFIG,
            stream_mode='messages'
        ):
            response_text += message_chunk.content
            response_placeholder.markdown(response_text)

        ai_message = response_text
        
    st.session_state['message_history'].append({'role':'assistant', 'content': ai_message})
    if is_first_message:
        st.rerun()
