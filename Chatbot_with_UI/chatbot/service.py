"""Conversation operations and backend resource ownership."""

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from chatbot.config import DATABASE_PATH, ENV_PATH
from chatbot.graph import build_chatbot


def thread_config(thread_id: str) -> RunnableConfig:
    """Build the checkpoint configuration used by every conversation operation."""
    return {"configurable": {"thread_id": thread_id}}


@dataclass
class ChatService:
    """Expose conversations without coupling callers to checkpoint internals."""

    graph: CompiledStateGraph
    checkpointer: BaseCheckpointSaver
    connection: sqlite3.Connection | None = field(default=None, repr=False)

    def list_threads(self) -> list[str]:
        """Return unique thread IDs in the checkpointer's newest-first order."""
        return list(
            dict.fromkeys(
                str(checkpoint.config["configurable"]["thread_id"])
                for checkpoint in self.checkpointer.list(None)
            )
        )

    def load_messages(self, thread_id: str) -> list[BaseMessage]:
        """Read saved messages, returning an empty list for a new thread."""
        return self.graph.get_state(thread_config(thread_id)).values.get("messages", [])

    def stream_response(self, thread_id: str, prompt: str) -> Iterator[str]:
        """Yield assistant text as the graph processes a user message."""
        for message, _metadata in self.graph.stream(
            {"messages": [HumanMessage(content=prompt)]},
            config=thread_config(thread_id),
            stream_mode="messages",
        ):
            if message.text:
                yield message.text

    def close(self) -> None:
        """Release the owned database connection; safe to call more than once."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def create_model() -> BaseChatModel:
    """Load local configuration only when a real model is needed."""
    load_dotenv(ENV_PATH)
    return ChatOpenAI()


def create_memory_service(model: BaseChatModel | None = None) -> ChatService:
    """Create a backend whose checkpoints last for the current process."""
    if model is None:
        model = create_model()
    checkpointer = InMemorySaver()
    return ChatService(build_chatbot(model, checkpointer), checkpointer)


def create_sqlite_service(
    database_path: Path = DATABASE_PATH,
    model: BaseChatModel | None = None,
) -> ChatService:
    """Open a persistent backend, allowing temporary databases and test models."""
    if model is None:
        model = create_model()
    connection = sqlite3.connect(database=database_path, check_same_thread=False)
    try:
        checkpointer = SqliteSaver(conn=connection)
        graph = build_chatbot(model, checkpointer)
    except Exception:
        connection.close()
        raise
    return ChatService(graph, checkpointer, connection)
