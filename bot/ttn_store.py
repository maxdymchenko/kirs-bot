"""Локальне сховище PDF накладних: data/ttn_pdfs/ДД.ММ.РРРР/файл.pdf"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")


def day_folder_name(now: datetime | None = None) -> str:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    return dt.strftime("%d.%m.%Y")


def _root_dir() -> Path:
    base = (os.getenv("APP_DATA_DIR") or "").strip()
    if base:
        root = Path(base) / "ttn_pdfs"
    else:
        root = Path(__file__).resolve().parent.parent / "data" / "ttn_pdfs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_day_dir(now: datetime | None = None) -> Path:
    day = _root_dir() / day_folder_name(now)
    day.mkdir(parents=True, exist_ok=True)
    return day


def _safe_filename(*parts: str) -> str:
    raw = "_".join(str(p or "").strip() for p in parts if str(p or "").strip())
    raw = re.sub(r"[^\w.\-А-Яа-яЁёІіЇїЄє]+", "_", raw, flags=re.UNICODE)
    raw = raw.strip("._") or "ttn"
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    return raw[:180]


def save_pdf_bytes(
    data: bytes,
    *,
    filename: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not data:
        raise ValueError("Порожній PDF")
    day = ensure_day_dir(now)
    name = _safe_filename(filename)
    path = day / name
    path.write_bytes(data)
    rel = f"{day.name}/{name}"
    return {
        "path": str(path),
        "relative": rel,
        "folder_name": day.name,
        "name": name,
        "bytes": len(data),
    }


def read_pdf_bytes(relative_or_abs: str) -> bytes:
    raw = str(relative_or_abs or "").strip()
    if not raw:
        raise ValueError("Немає шляху до PDF")
    path = Path(raw)
    if not path.is_file():
        # relative to ttn_pdfs root: 26.07.2026/file.pdf
        path = _root_dir() / raw.replace("\\", "/")
    if not path.is_file():
        raise FileNotFoundError(f"PDF не знайдено: {raw}")
    return path.read_bytes()
