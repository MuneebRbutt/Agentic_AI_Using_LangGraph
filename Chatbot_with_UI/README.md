# LangGraph Chatbot

A Streamlit chatbot with a shared LangGraph conversation graph and two interfaces:
a styled interface with SQLite persistence and a minimal in-memory tutorial.

## Setup

Use Python 3.11 or newer. From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Chatbot_with_UI/requirements-dev.txt
```

Create `Chatbot_with_UI/.env` using `.env.example` as a template and set
`OPENAI_API_KEY`. An environment variable of the same name also works and takes
precedence over the file.

## Run

```powershell
# Persistent interface
.\.venv\Scripts\python.exe -m streamlit run Chatbot_with_UI/app.py

# In-memory tutorial interface
.\.venv\Scripts\python.exe -m streamlit run Chatbot_with_UI/streamlit_frontend.py
```

`streamlit_database_frontend.py` remains a supported entry point for existing
deployments. Launching these scripts from inside `Chatbot_with_UI` also works.
SQLite conversations remain in `Chatbot_with_UI/chatbot.db`; paths do not depend
on the directory from which the app is launched. Memory-mode conversations last
only for the current server process and are listed within their browser session.

## Structure

```text
Chatbot_with_UI/
├── app.py                         # Persistent app entry point
├── streamlit_database_frontend.py # Existing deployment entry point
├── streamlit_frontend.py          # In-memory app entry point
├── langgraph_backend.py           # Legacy backend imports
├── langgraph_database_backend.py  # Legacy backend imports
├── chatbot/
│   ├── config.py                  # Paths for configuration and assets
│   ├── conversations.py           # Titles and thread identifiers
│   ├── graph.py                   # Typed state and graph construction
│   ├── service.py                 # Conversation operations and backend factories
│   └── ui/
│       ├── app.py                 # Persistent page composition
│       ├── components.py          # Styled rendering and input handlers
│       ├── memory_app.py          # Minimal tutorial interface
│       ├── resources.py           # Cached service lifecycle
│       └── state.py               # Session initialization and chat selection
├── tests/                        # Offline persistence and interface tests
└── style.css                     # Existing presentation styles
```

The backend modules do not depend on Streamlit. Factories accept an injected
model and database path, so tests run without API calls or access to saved chats.
Services own their SQLite connections; callers outside Streamlit should call
`service.close()` when finished. The UI caches services across reruns and closes
them at process exit. The legacy backend modules retain their original
import-time initialization for compatibility; prefer factories in new code.

## Development checks

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s Chatbot_with_UI/tests -v
.\.venv\Scripts\python.exe -m ruff check Chatbot_with_UI
.\.venv\Scripts\python.exe -m ruff format --check Chatbot_with_UI
```

The root `pyproject.toml` defines formatting and import-order rules. Tutorial
notebooks remain at the repository root, separate from the application package.
