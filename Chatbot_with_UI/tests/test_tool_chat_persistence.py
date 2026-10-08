"""Real SQLite and Streamlit refresh tests; no API keys or network calls."""

import ast
import asyncio
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import aiosqlite
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
from chat_persistence import database_path


class PersistenceCases:
    asynchronous = False

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / 'chatbot.db'
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_loop)
        self.backend_name = ('langgraph_mcp_backend' if self.asynchronous
                             else 'langgraph_tool_backend')
        self.frontend = ('streamlit_frontend_mcp.py' if self.asynchronous
                         else 'streamlit_frontend.py')
        self.backend = types.ModuleType(self.backend_name)
        self.backend.run_async = self.run_async
        self.backend.submit_async_task = self.submit
        self.open_backend()
        self.addCleanup(self.close_backend)
        # Use the production thread-list functions with the temporary checkpointer.
        tree = ast.parse((APP_DIR / f'{self.backend_name}.py').read_text())
        functions = [node for node in tree.body if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name in {'retrieve_all_threads', '_alist_threads'}]
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<thread helpers>', 'exec'),
             self.backend.__dict__)
        previous_backend = sys.modules.get(self.backend_name)
        sys.modules[self.backend_name] = self.backend
        def restore_backend():
            if previous_backend is None:
                sys.modules.pop(self.backend_name, None)
            else:
                sys.modules[self.backend_name] = previous_backend
        self.addCleanup(restore_backend)

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def run_async(self, coroutine):
        return self.submit(coroutine).result(timeout=10)

    def close_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()

    def open_backend(self):
        model = FakeListChatModel(responses=['Saved reply'])
        if self.asynchronous:
            async def connect():
                connection = await aiosqlite.connect(self.database)
                return connection, AsyncSqliteSaver(connection)
            self.connection, saver = self.run_async(connect())

            async def answer(state):
                return {'messages': [await model.ainvoke(state['messages'])]}
        else:
            self.connection = sqlite3.connect(self.database, check_same_thread=False)
            saver = SqliteSaver(self.connection)

            def answer(state):
                return {'messages': [model.invoke(state['messages'])]}

        graph = StateGraph(MessagesState)
        graph.add_node('chat_node', answer)
        graph.add_edge(START, 'chat_node')
        graph.add_edge('chat_node', END)
        self.backend.chatbot = graph.compile(checkpointer=saver)
        self.backend.checkpointer = saver

    def close_backend(self):
        if self.asynchronous:
            self.run_async(self.connection.close())
        else:
            self.connection.close()

    def save_chat(self, thread_id, text):
        values = {'messages': [HumanMessage(text)]}
        config = {'configurable': {'thread_id': thread_id}}
        if self.asynchronous:
            self.run_async(self.backend.chatbot.ainvoke(values, config))
        else:
            self.backend.chatbot.invoke(values, config)

    def open_app(self, query=None):
        app = AppTest.from_file(str(APP_DIR / self.frontend), default_timeout=10)
        app.query_params.update(query or {})
        app.run()
        self.assertFalse(app.exception)
        return app

    def contents(self, app):
        return [message['content'] for message in app.session_state['message_history']]

    def test_refresh_restores_titles_and_latest_chat(self):
        self.save_chat('older', 'First conversation')
        self.save_chat('newer', 'New Chat')
        app = self.open_app()
        self.assertEqual(self.backend.retrieve_all_threads(), ['newer', 'older'])
        self.assertEqual(app.sidebar.button(key='chat_newer').label, 'New Chat')
        self.assertEqual(app.sidebar.button(key='chat_older').label, 'First conversation')
        self.assertEqual(self.contents(app), ['New Chat', 'Saved reply'])
        self.assertEqual([m.name for m in app.chat_message], ['user', 'assistant'])

    def test_selected_chat_and_followup_survive_refresh(self):
        self.save_chat('older', 'First conversation')
        self.save_chat('newer', 'Second conversation')
        app = self.open_app()
        app.sidebar.button(key='chat_older').click().run()
        self.assertFalse(app.exception)
        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(refreshed.session_state['thread_id'], 'older')
        self.assertEqual(self.contents(refreshed), ['First conversation', 'Saved reply'])
        refreshed.chat_input[0].set_value('Follow-up').run()
        self.assertFalse(refreshed.exception)
        after_send = self.open_app(dict(refreshed.query_params))
        self.assertEqual(self.contents(after_send), [
            'First conversation', 'Saved reply', 'Follow-up', 'Saved reply',
        ])

    def test_empty_new_chat_survives_refresh_and_then_is_saved(self):
        self.save_chat('saved', 'Existing conversation')
        app = self.open_app()
        app.sidebar.button[0].click().run()
        empty_id = app.session_state['thread_id']
        app.sidebar.button[0].click().run()
        self.assertEqual(app.session_state['thread_id'], empty_id)
        refreshed = self.open_app(dict(app.query_params))
        self.assertEqual(refreshed.session_state['thread_id'], empty_id)
        self.assertEqual(len(refreshed.chat_message), 0)
        self.assertEqual(len(refreshed.sidebar.button), 2)
        refreshed.chat_input[0].set_value('New question').run()
        self.assertFalse(refreshed.exception)
        self.assertEqual(refreshed.sidebar.button(key=f'chat_{empty_id}').label, 'New question')
        after_send = self.open_app(dict(refreshed.query_params))
        self.assertEqual(self.contents(after_send), ['New question', 'Saved reply'])

    def test_empty_database(self):
        app = self.open_app()
        self.assertEqual(len(app.sidebar.button), 1)
        self.assertEqual(len(app.chat_message), 0)
        self.assertIsInstance(app.session_state['thread_id'], str)

    def test_invalid_url_falls_back_to_latest_chat(self):
        self.save_chat('saved', 'Existing conversation')
        app = self.open_app({'thread_id': 'invalid/missing'})
        self.assertEqual(app.session_state['thread_id'], 'saved')

    def test_database_reopen_preserves_history(self):
        self.save_chat('saved', 'Remember this conversation')
        self.close_backend()
        self.open_backend()
        app = self.open_app({'thread_id': 'saved'})
        self.assertEqual(self.contents(app), ['Remember this conversation', 'Saved reply'])

    def test_restored_tool_outputs_are_hidden(self):
        messages = [
            HumanMessage('Calculate 2 + 3'),
            AIMessage('', tool_calls=[{'name': 'calculator', 'args': {}, 'id': 'call-1'}]),
            ToolMessage('RAW TOOL JSON', tool_call_id='call-1'),
            AIMessage('The answer is 5.'),
        ]
        config = {'configurable': {'thread_id': 'tools'}}
        if self.asynchronous:
            self.run_async(self.backend.chatbot.aupdate_state(config, {'messages': messages}))
        else:
            self.backend.chatbot.update_state(config, {'messages': messages})
        app = self.open_app()
        self.assertEqual(self.contents(app), ['Calculate 2 + 3', 'The answer is 5.'])
        self.assertEqual(len(app.chat_message), 2)
        self.assertEqual(app.session_state['message_history'][-1]['tools_used'], ['calculator'])


class ToolChatPersistenceTests(PersistenceCases, unittest.TestCase):
    pass


class MCPChatPersistenceTests(PersistenceCases, unittest.TestCase):
    asynchronous = True


class DatabasePathTests(unittest.TestCase):
    def test_app_database_used_without_legacy_database(self):
        with patch('chat_persistence.Path.is_file', return_value=False):
            self.assertEqual(database_path(), APP_DIR / 'chatbot.db')

    def test_existing_root_database_is_preserved(self):
        with patch('chat_persistence.Path.is_file', return_value=True):
            self.assertEqual(database_path(), APP_DIR.parent / 'chatbot.db')


if __name__ == '__main__':
    unittest.main()
