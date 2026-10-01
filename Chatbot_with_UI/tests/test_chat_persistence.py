"""Run with: python -m unittest discover -s Chatbot_with_UI/tests -v

Uses a temporary SQLite database and a fake model; no API calls or user data.
"""

import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from streamlit.testing.v1 import AppTest


APP_DIR = Path(__file__).resolve().parents[1]


class ChatPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / 'chatbot.db'
        self.real_connect = sqlite3.connect
        self.backend = self.load_backend()

    def load_backend(self):
        spec = importlib.util.spec_from_file_location(
            'langgraph_database_backend', APP_DIR / 'langgraph_database_backend.py'
        )
        backend = importlib.util.module_from_spec(spec)
        module_patch = patch.dict(sys.modules, {spec.name: backend})
        module_patch.start()
        self.addCleanup(module_patch.stop)

        def connect(database, **kwargs):
            self.assertEqual(Path(database), APP_DIR / 'chatbot.db')
            return self.real_connect(self.database, **kwargs)

        with patch('sqlite3.connect', side_effect=connect), patch(
            'langchain_openai.ChatOpenAI', return_value=FakeListChatModel(responses=['Saved reply'])
        ), patch('dotenv.load_dotenv'):
            spec.loader.exec_module(backend)
        self.addCleanup(backend.conn.close)
        return backend

    def save_chat(self, thread_id, message):
        self.backend.chatbot.invoke(
            {'messages': [HumanMessage(content=message)]},
            config={'configurable': {'thread_id': thread_id}},
        )

    def open_app(self, query_params=None):
        app = AppTest.from_file(str(APP_DIR / 'streamlit_database_frontend.py'))
        app.query_params.update(query_params or {})
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_fresh_session_restores_titles_and_latest_history(self):
        self.save_chat('older', '  First   conversation  ')
        self.save_chat('newer', 'New Chat')
        app = self.open_app()
        self.assertEqual(self.backend.retrieve_all_threads(), ['newer', 'older'])
        self.assertEqual(app.sidebar.button(key='chat_older').label, 'First conversation')
        # A real conversation named New Chat must not be hidden as a placeholder.
        self.assertEqual(app.sidebar.button(key='chat_newer').label, 'New Chat')
        self.assertEqual(app.session_state['thread_id'], 'newer')
        self.assertEqual([message.value for message in app.text], ['New Chat', 'Saved reply'])

    def test_refresh_keeps_selected_chat_and_continues_its_history(self):
        self.save_chat('older', 'First conversation')
        self.save_chat('newer', 'Second conversation')
        app = self.open_app()
        app.sidebar.button(key='chat_older').click().run()
        self.assertFalse(app.exception)

        # Browser refresh keeps the URL but discards all Streamlit session state.
        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(refreshed.session_state['thread_id'], 'older')
        self.assertEqual([message.value for message in refreshed.text], ['First conversation', 'Saved reply'])
        refreshed.chat_input[0].set_value('Follow-up').run()
        self.assertFalse(refreshed.exception)

        refreshed_again = self.open_app(dict(refreshed.query_params))
        self.assertEqual([message.value for message in refreshed_again.text], [
            'First conversation', 'Saved reply', 'Follow-up', 'Saved reply',
        ])
        self.assertEqual(refreshed_again.sidebar.button(key='chat_older').label, 'First conversation')

    def test_empty_new_chat_survives_refresh_without_duplicate_buttons(self):
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
        self.assertEqual(refreshed.sidebar.button(key=f'chat_{empty_thread}').label, 'A new conversation')
        after_send = self.open_app(dict(refreshed.query_params))
        self.assertEqual([message.value for message in after_send.text], ['A new conversation', 'Saved reply'])

    def test_invalid_url_falls_back_to_saved_chat(self):
        self.save_chat('saved', 'Existing conversation')
        app = self.open_app({'thread_id': 'invalid/missing'})
        self.assertEqual(app.session_state['thread_id'], 'saved')

    def test_empty_database_starts_one_empty_chat(self):
        app = self.open_app()
        self.assertEqual(len(app.sidebar.button), 1)
        self.assertEqual(len(app.chat_message), 0)
        self.assertIsInstance(app.session_state['thread_id'], str)

    def test_history_survives_backend_restart(self):
        self.save_chat('saved', 'Remember this conversation')
        self.backend.conn.close()
        self.backend = self.load_backend()
        app = self.open_app({'thread_id': 'saved'})
        self.assertEqual([message.value for message in app.text], ['Remember this conversation', 'Saved reply'])


if __name__ == '__main__':
    unittest.main()
