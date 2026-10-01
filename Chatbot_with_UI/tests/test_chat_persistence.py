"""Run with: python -m unittest discover -s Chatbot_with_UI/tests -v

Uses a temporary SQLite database and a fake model; no API calls or user data.
"""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from streamlit.testing.v1 import AppTest


APP_DIR = Path(__file__).resolve().parents[1]


# The app directory is the import root used by Streamlit entry points.
sys.path.insert(0, str(APP_DIR))

from chatbot.service import ChatService, create_sqlite_service, thread_config  # noqa: E402


class ChatPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / "chatbot.db"
        self.backend = self.load_backend()
        service_patch = patch(
            "chatbot.ui.app.get_chat_service", side_effect=lambda: self.backend
        )
        service_patch.start()
        self.addCleanup(service_patch.stop)

    def load_backend(self) -> ChatService:
        service = create_sqlite_service(
            self.database, model=FakeListChatModel(responses=["Saved reply"])
        )
        self.addCleanup(service.close)
        return service

    def message_contents(self, app: AppTest) -> list[str]:
        return [message.markdown[0].value for message in app.chat_message]

    def save_chat(self, thread_id: str, message: str) -> None:
        self.backend.graph.invoke(
            {'messages': [HumanMessage(content=message)]},
            config=thread_config(thread_id),
        )

    def open_app(self, query_params: dict | None = None) -> AppTest:
        app = AppTest.from_file(str(APP_DIR / 'streamlit_database_frontend.py'))
        app.query_params.update(query_params or {})
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_fresh_session_restores_titles_and_latest_history(self) -> None:
        self.save_chat('older', '  First   conversation  ')
        self.save_chat('newer', 'New Chat')
        app = self.open_app()
        self.assertEqual(self.backend.list_threads(), ['newer', 'older'])
        self.assertEqual(app.sidebar.button(key='chat_older').help, 'First conversation')
        # A real conversation named New Chat must not be hidden as a placeholder.
        self.assertEqual(app.sidebar.button(key='chat_newer').help, 'New Chat')
        self.assertEqual(app.session_state['thread_id'], 'newer')
        self.assertEqual(self.message_contents(app), ['New Chat', 'Saved reply'])

    def test_refresh_keeps_selected_chat_and_continues_its_history(self) -> None:
        self.save_chat('older', 'First conversation')
        self.save_chat('newer', 'Second conversation')
        app = self.open_app()
        app.sidebar.button(key='chat_older').click().run()
        self.assertFalse(app.exception)

        # Browser refresh keeps the URL but discards all Streamlit session state.
        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(refreshed.session_state['thread_id'], 'older')
        self.assertEqual(self.message_contents(refreshed), ['First conversation', 'Saved reply'])
        refreshed.chat_input[0].set_value('Follow-up').run()
        self.assertFalse(refreshed.exception)

        refreshed_again = self.open_app(dict(refreshed.query_params))
        self.assertEqual(self.message_contents(refreshed_again), [
            'First conversation', 'Saved reply', 'Follow-up', 'Saved reply',
        ])
        self.assertEqual(refreshed_again.sidebar.button(key='chat_older').help, 'First conversation')

    def test_empty_new_chat_survives_refresh_without_duplicate_buttons(self) -> None:
        self.save_chat('saved', 'Existing conversation')
        app = self.open_app()
        app.sidebar.button[0].click().run()
        empty_thread = app.session_state['thread_id']
        self.assertNotEqual(empty_thread, 'saved')
        app.sidebar.button[0].click().run()
        self.assertEqual(app.session_state['thread_id'], empty_thread)

        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(refreshed.session_state['thread_id'], empty_thread)
        self.assertEqual(len(refreshed.chat_message), 0)
        self.assertEqual(len(refreshed.sidebar.button), 2)
        refreshed.chat_input[0].set_value('A new conversation').run()
        self.assertFalse(refreshed.exception)
        self.assertEqual(refreshed.sidebar.button(key=f'chat_{empty_thread}').help, 'A new conversation')
        after_send = self.open_app(dict(refreshed.query_params))
        self.assertEqual(self.message_contents(after_send), ['A new conversation', 'Saved reply'])

    def test_invalid_url_falls_back_to_saved_chat(self) -> None:
        self.save_chat('saved', 'Existing conversation')
        app = self.open_app({'thread_id': 'invalid/missing'})
        self.assertEqual(app.session_state['thread_id'], 'saved')

    def test_empty_database_starts_one_empty_chat(self) -> None:
        app = self.open_app()
        self.assertEqual(len(app.sidebar.button), 1)
        self.assertEqual(len(app.chat_message), 0)
        self.assertIsInstance(app.session_state['thread_id'], str)

    def test_history_survives_backend_restart(self) -> None:
        self.save_chat('saved', 'Remember this conversation')
        self.backend.close()
        self.backend = self.load_backend()
        app = self.open_app({'thread_id': 'saved'})
        self.assertEqual(self.message_contents(app), ['Remember this conversation', 'Saved reply'])


    def test_primary_entry_point_uses_the_same_saved_conversation(self) -> None:
        self.save_chat("saved", "Existing conversation")
        app = AppTest.from_file(str(APP_DIR / "app.py")).run()
        self.assertFalse(app.exception)
        self.assertEqual(self.message_contents(app), ["Existing conversation", "Saved reply"])

    def test_suggestion_streams_and_persists_a_conversation(self) -> None:
        app = self.open_app()
        app.button(key="suggestion-✦  Explain a concept").click().run()
        self.assertFalse(app.exception)
        thread_id = app.session_state["thread_id"]
        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(
            self.message_contents(refreshed),
            ["Explain a concept in simple terms, with an example.", "Saved reply"],
        )
        self.assertEqual(self.backend.list_threads(), [thread_id])


if __name__ == '__main__':
    unittest.main()
