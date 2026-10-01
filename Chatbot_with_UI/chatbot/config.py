"""Application paths, resolved independently of the working directory."""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = APP_DIR / "chatbot.db"
ENV_PATH = APP_DIR / ".env"
STYLESHEET_PATH = APP_DIR / "style.css"
