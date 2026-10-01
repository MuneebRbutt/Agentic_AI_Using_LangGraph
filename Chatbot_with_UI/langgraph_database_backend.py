from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from pathlib import Path
import sqlite3

load_dotenv()
model = ChatOpenAI()

class ChatState(TypedDict):
    
    messages : Annotated[list[BaseMessage], add_messages]
    
def chat_node(state: ChatState):
    messages = state['messages']
    # Creating a state for maintaining the messagess
    
    response = model.invoke(messages)
    
    return {'messages': [response]}

DATABASE_PATH = Path(__file__).resolve().with_name('chatbot.db')
conn = sqlite3.connect(database=DATABASE_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)

graph.add_node('chat_node', chat_node)

graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatbot = graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    # SqliteSaver lists newest checkpoints first. Preserve that order while
    # deduplicating threads so the latest conversation can be restored.
    all_threads = {}
    for checkpoint in checkpointer.list(None):
        all_threads.setdefault(str(checkpoint.config['configurable']['thread_id']), None)
    return list(all_threads)
