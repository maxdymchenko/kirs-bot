"""Локальне сховище PDF накладних: data/ttn_pdfs/ДД.ММ.РРРР/файл.pdf"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
_DAY_FOLDER_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
DEFAULT_RETAIN_DAYS = 10


def day_folder_name(now: datetime | None = None) -> str:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    return dt.strftime("%d.%m.%Y")


def retain_days() -> int:
    raw = (os.getenv("TTN_PDF_RETAIN_DAYS") or "").strip()
    if not raw:
        return DEFAULT_RETAIN_DAYS
    try:
        return max(1, min(365, int(raw)))
    except ValueError:
        return DEFAULT_RETAIN_DAYS


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


def _parse_day_folder(name: str) -> date | None:
    match = _DAY_FOLDER_RE.match(str(name or "").strip())
    if not match:
        return None
    day_s, month_s, year_s = match.groups()
    try:
        return date(int(year_s), int(month_s), int(day_s))
    except ValueError:
        return None


def cleanup_old_ttn_pdfs(
    *,
    days: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Видалити денні папки накладних старші за N днів (за назвою ДД.ММ.РРРР).
    За замовчуванням N=10: папка від 16.07 видалиться 26.07.
    """
    keep = retain_days() if days is None else max(1, int(days))
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    today = dt.date()
    cutoff = today - timedelta(days=keep)

    root = _root_dir()
    deleted: list[str] = []
    kept = 0
    skipped = 0
    for child in root.iterdir():
        if not child.is_dir():
            skipped += 1
            continue
        folder_day = _parse_day_folder(child.name)
        if folder_day is None:
            skipped += 1
            continue
        if folder_day <= cutoff:
            try:
                shutil.rmtree(child)
                deleted.append(child.name)
            except Exception:
                logger.exception("ttn pdf cleanup failed folder=%s", child)
        else:
            kept += 1

    stats = {
        "retain_days": keep,
        "cutoff": cutoff.isoformat(),
        "deleted": deleted,
        "deleted_count": len(deleted),
        "kept": kept,
        "skipped": skipped,
    }
    if deleted:
        logger.info("TTN PDF cleanup: removed %s (cutoff=%s)", deleted, cutoff)
    else:
        logger.info(
            "TTN PDF cleanup: nothing to remove (retain=%s cutoff=%s kept=%s)",
            keep,
            cutoff,
            kept,
        )
    return stats
