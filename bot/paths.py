"""Пути к данным. APP_DATA_DIR — точка монтирования Render Disk."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    raw = (os.getenv("APP_DATA_DIR") or "").strip()
    path = Path(raw) if raw else Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_db_path() -> Path:
    return data_dir() / "app.db"


def notifications_db_path() -> Path:
    return data_dir() / "notifications.db"
