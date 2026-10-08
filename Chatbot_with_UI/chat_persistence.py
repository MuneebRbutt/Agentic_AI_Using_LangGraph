"""Restore the tool and MCP chat interfaces from checkpointed conversations."""

from pathlib import Path
import uuid

from langchain_core.messages import AIMessage, HumanMessage


def database_path():
    app_dir = Path(__file__).resolve().parent
    # Older deployments launched from the repository root saved their chats here.
    # Keep using that database when present, regardless of the working directory.
    legacy_path = app_dir.parent / 'chatbot.db'
    return legacy_path if legacy_path.is_file() else app_dir / 'chatbot.db'


def conversation_title(text):
    title = ' '.join(text.split())
    return title[:40] + ('...' if len(title) > 40 else '') or 'New Chat'


def visible_messages(messages):
    history = []
    tools_used = []
    for message in messages:
        if isinstance(message, HumanMessage):
            tools_used = []
            history.append({'role': 'user', 'content': message.content})
        elif isinstance(message, AIMessage):
            if message.tool_calls:
                for call in message.tool_calls:
                    if call['name'] not in tools_used:
                        tools_used.append(call['name'])
            else:
                history.append({
                    'role': 'assistant', 'content': message.content,
                    'tools_used': list(tools_used),
                })
    return history


def select_conversation(state, query_params, thread_id, load_conversation):
    state['thread_id'] = str(thread_id)
    query_params['thread_id'] = str(thread_id)
    state['message_history'] = visible_messages(load_conversation(str(thread_id)))


def initialize_history(state, query_params, retrieve_all_threads, load_conversation):
    if 'chat_threads' not in state:
        state['chat_threads'] = list(dict.fromkeys(map(str, retrieve_all_threads())))

    if 'chat_titles' not in state:
        state['chat_titles'] = {}
        for thread_id in state['chat_threads']:
            for message in load_conversation(thread_id):
                if isinstance(message, HumanMessage):
                    state['chat_titles'][thread_id] = conversation_title(message.text)
                    break

    if 'thread_id' not in state:
        requested = query_params.get('thread_id')
        if requested not in state['chat_threads']:
            # A new empty chat has no checkpoint, but its UUID survives in the URL.
            try:
                requested = str(uuid.UUID(requested))
            except (ValueError, TypeError, AttributeError):
                requested = next(iter(state['chat_titles']), str(uuid.uuid4()))
        state['thread_id'] = requested

    if 'message_history' not in state:
        select_conversation(state, query_params, state['thread_id'], load_conversation)


def new_conversation(state, query_params):
    if state['message_history']:
        state['thread_id'] = str(uuid.uuid4())
    state['message_history'] = []
    query_params['thread_id'] = state['thread_id']
