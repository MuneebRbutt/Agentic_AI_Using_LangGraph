"""Offline coverage for shared graph behavior and compatibility entry points."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from chatbot.service import create_memory_service  # noqa: E402


class BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_memory_service(
            model=FakeListChatModel(responses=["Test reply"])
        )
        self.addCleanup(self.service.close)

    def test_streaming_persists_messages_and_isolates_threads(self) -> None:
        self.assertEqual(
            "".join(self.service.stream_response("first", "Hello")), "Test reply"
        )
        self.assertEqual(
            "".join(self.service.stream_response("second", "Separate chat")),
            "Test reply",
        )
        self.assertEqual(
            [message.content for message in self.service.load_messages("first")],
            ["Hello", "Test reply"],
        )
        self.assertEqual(self.service.load_messages("missing"), [])
        self.assertCountEqual(self.service.list_threads(), ["first", "second"])

    def test_legacy_backend_exports_use_shared_factories(self) -> None:
        for filename, factory in (
            ("langgraph_backend.py", "create_memory_service"),
            ("langgraph_database_backend.py", "create_sqlite_service"),
        ):
            with self.subTest(filename=filename):
                spec = importlib.util.spec_from_file_location(
                    "legacy_backend", APP_DIR / filename
                )
                module = importlib.util.module_from_spec(spec)
                with patch(f"chatbot.service.{factory}", return_value=self.service):
                    spec.loader.exec_module(module)
                self.assertIs(module.chatbot, self.service.graph)
                self.assertIs(module.checkpointer, self.service.checkpointer)
                if filename == "langgraph_database_backend.py":
                    self.assertEqual(module.retrieve_all_threads(), [])
                    self.assertEqual(module.DATABASE_PATH, APP_DIR / "chatbot.db")

    def test_memory_interface_can_send_select_and_reset(self) -> None:
        with patch("chatbot.ui.memory_app.get_chat_service", return_value=self.service):
            app = AppTest.from_file(str(APP_DIR / "streamlit_frontend.py")).run()
            self.assertFalse(app.exception)
            app.chat_input[0].set_value("Hello").run()
            self.assertFalse(app.exception)
            saved_thread = app.session_state["thread_id"]
            self.assertEqual(len(app.chat_message), 2)

            app.sidebar.button[0].click().run()
            empty_thread = app.session_state["thread_id"]
            self.assertNotEqual(empty_thread, saved_thread)
            app.sidebar.button[0].click().run()
            self.assertEqual(app.session_state["thread_id"], empty_thread)

            app.sidebar.button(key=f"chat_{saved_thread}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["thread_id"], saved_thread)
            self.assertEqual([message.value for message in app.text], ["Hello", "Test reply"])


if __name__ == "__main__":
    unittest.main()
