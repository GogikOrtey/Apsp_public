"""
WSGI entrypoint for production server (Gunicorn).

Important: we load `.env` BEFORE importing `Apsp_front.app`, because that module
reads APSP_TELEGRAM_* and other env vars during import time.
"""

from __future__ import annotations

from pathlib import Path


def _load_dotenv_best_effort() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


_load_dotenv_best_effort()

# Flask application object for gunicorn: `wsgi:app`
from Apsp_front.app import app  # noqa: E402  (import after dotenv)


