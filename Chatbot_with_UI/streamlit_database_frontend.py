import streamlit as st 
from langgraph_database_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage
import uuid # Importing this to generate dynamic threadids rather than hardcoating it for each conversation.



# Utility Functions
def generate_thread_id():
    return str(uuid.uuid4())


def conversation_title(text):
    title = " ".join(text.split())
    return title[:40] + ("..." if len(title) > 40 else "") or "New Chat"

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
    st.query_params['thread_id'] = thread_id
    
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

# This function is loading conversations respectively.       
def load_conversation(thread_id):
    return chatbot.get_state(config={'configurable': {'thread_id': thread_id}}).values.get('messages', [])


def select_conversation(thread_id):
    st.session_state['thread_id'] = thread_id
    st.query_params['thread_id'] = thread_id
    st.session_state['message_history'] = [
        {'role': 'user' if isinstance(message, HumanMessage) else 'assistant',
         'content': message.content}
        for message in load_conversation(thread_id)
    ]


if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()    

# Session state is lost on refresh. Rebuild titles from persisted messages.
if 'chat_titles' not in st.session_state:
    st.session_state['chat_titles'] = {}
    for thread_id in st.session_state['chat_threads']:
        for message in load_conversation(thread_id):
            if isinstance(message, HumanMessage):
                st.session_state['chat_titles'][thread_id] = conversation_title(message.content)
                break

if 'thread_id' not in st.session_state:
    requested_thread = st.query_params.get('thread_id')
    if requested_thread not in st.session_state['chat_threads']:
        # An empty New Chat has no checkpoint yet, but its UUID can survive refresh.
        try:
            requested_thread = str(uuid.UUID(requested_thread))
        except (ValueError, TypeError, AttributeError):
            requested_thread = next(iter(st.session_state['chat_titles']), generate_thread_id())
    st.session_state['thread_id'] = requested_thread

add_thread(st.session_state['thread_id'])

if 'message_history' not in st.session_state:
    select_conversation(st.session_state['thread_id'])
    
    
    
st.sidebar.title("Langgraph Chatbot")   
if st.sidebar.button("New Chat"):
    reset_chat() 

st.sidebar.header("My Conversations")

for thread_id in st.session_state['chat_threads']:
    title = st.session_state['chat_titles'].get(thread_id)

    # Empty chats are available through the main New Chat button, so do not
    # list their placeholder title as a conversation.
    if title is None:
        continue

    if st.sidebar.button(title, key=f"chat_{thread_id}"):
        select_conversation(thread_id)

CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input('Type Here')

if user_input:
    is_first_message = len(st.session_state['message_history']) == 0

    if is_first_message:
        st.session_state['chat_titles'][
            st.session_state['thread_id']
        ] = conversation_title(user_input)
    
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
        
        
