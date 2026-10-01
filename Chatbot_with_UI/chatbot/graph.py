"""Build the conversation graph with an injected model and checkpointer."""

from typing import Annotated, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph


class ChatState(TypedDict):
    """Conversation messages accumulated across graph invocations."""

    messages: Annotated[list[BaseMessage], add_messages]


def build_chatbot(
    model: BaseChatModel, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    """Compile the shared graph for either memory or SQLite persistence."""

    def chat_node(state: ChatState) -> ChatState:
        return {"messages": [model.invoke(state["messages"])]}

    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_edge(START, "chat_node")
    graph.add_edge("chat_node", END)
    return graph.compile(checkpointer=checkpointer)
