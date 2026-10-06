"""Compatibility entry point for existing Streamlit Cloud deployments.

The presentation is maintained in app.py. Keep this entry point so an app
already configured with this filename receives the redesigned interface too.
"""

from pathlib import Path


app_path = Path(__file__).with_name("app.py")
exec(compile(app_path.read_text(encoding="utf-8"), str(app_path), "exec"))
