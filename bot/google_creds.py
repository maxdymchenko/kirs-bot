"""Спільні credentials Google (Sheets + Drive)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2.service_account import Credentials

DEFAULT_CREDS_FILE = (
    Path(__file__).resolve().parent.parent / "midyear-respect-502706-i6-c5ddff36cd28.json"
)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_google_credentials(scopes: list[str] | None = None) -> Credentials:
    use_scopes = list(scopes or DRIVE_SCOPES)
    json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if json_env:
        info = json.loads(json_env)
        return Credentials.from_service_account_info(info, scopes=use_scopes)
    path = Path(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip() or str(DEFAULT_CREDS_FILE)
    )
    if not path.exists():
        raise FileNotFoundError(
            f"Файл credentials не найден: {path}. "
            "Задайте GOOGLE_CREDENTIALS_FILE или GOOGLE_CREDENTIALS_JSON"
        )
    return Credentials.from_service_account_file(str(path), scopes=use_scopes)


def service_account_email() -> str:
    json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if json_env:
        info = json.loads(json_env)
        return str(info.get("client_email") or "")
    path = Path(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip() or str(DEFAULT_CREDS_FILE)
    )
    if not path.exists():
        return ""
    info = json.loads(path.read_text(encoding="utf-8"))
    return str(info.get("client_email") or "")
