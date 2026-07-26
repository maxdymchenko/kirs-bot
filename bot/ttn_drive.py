"""Збереження PDF накладних на Google Drive у денні папки (26.07.2026)."""

from __future__ import annotations

import io
import json
import logging
import os
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import AuthorizedSession

from bot.google_creds import load_google_credentials

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"


def day_folder_name(now: datetime | None = None) -> str:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    return dt.strftime("%d.%m.%Y")


def root_folder_id() -> str:
    return (
        os.getenv("TTN_DRIVE_ROOT_FOLDER_ID", "").strip()
        or os.getenv("STOCK_TTN_DRIVE_FOLDER_ID", "").strip()
    )


def _session() -> AuthorizedSession:
    creds = load_google_credentials()
    return AuthorizedSession(creds)


def _safe_filename(*parts: str) -> str:
    raw = "_".join(str(p or "").strip() for p in parts if str(p or "").strip())
    raw = re.sub(r"[^\w.\-А-Яа-яЁёІіЇїЄє]+", "_", raw, flags=re.UNICODE)
    raw = raw.strip("._") or "ttn"
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    return raw[:180]


def ensure_day_folder(
    *,
    parent_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    """Створити (або знайти) папку з назвою 26.07.2026 у кореневій теці Drive."""
    root = (parent_id or root_folder_id()).strip()
    if not root:
        raise RuntimeError(
            "Не задано TTN_DRIVE_ROOT_FOLDER_ID — папка Google Drive для накладних"
        )
    name = day_folder_name(now)
    session = _session()
    q = (
        f"name = '{name}' and '{root}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    resp = session.get(
        DRIVE_FILES,
        params={"q": q, "spaces": "drive", "fields": "files(id,name)", "pageSize": 5},
        timeout=30,
    )
    resp.raise_for_status()
    files = (resp.json() or {}).get("files") or []
    if files:
        folder_id = str(files[0].get("id") or "")
        return {"id": folder_id, "name": name, "created": False}

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [root],
    }
    create = session.post(
        DRIVE_FILES,
        params={"fields": "id,name"},
        headers={"Content-Type": "application/json; charset=UTF-8"},
        data=json.dumps(meta),
        timeout=30,
    )
    create.raise_for_status()
    data = create.json() or {}
    return {"id": str(data.get("id") or ""), "name": name, "created": True}


def upload_pdf_bytes(
    data: bytes,
    *,
    filename: str,
    folder_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Завантажити PDF у денну папку. Повертає {file_id, folder_id, folder_name, name}."""
    if not data:
        raise ValueError("Порожній PDF")
    day = ensure_day_folder(now=now)
    parent = folder_id or day["id"]
    name = _safe_filename(filename)
    session = _session()

    # Якщо файл з таким імʼям уже є — оновлюємо вміст
    q = (
        f"name = '{name.replace(chr(39), '')}' and '{parent}' in parents "
        "and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
    )
    existing = session.get(
        DRIVE_FILES,
        params={"q": q, "fields": "files(id,name)", "pageSize": 1},
        timeout=30,
    )
    existing.raise_for_status()
    files = (existing.json() or {}).get("files") or []
    if files:
        file_id = str(files[0].get("id") or "")
        upd = session.patch(
            f"{DRIVE_UPLOAD}/{file_id}",
            params={"uploadType": "media"},
            headers={"Content-Type": "application/pdf"},
            data=data,
            timeout=60,
        )
        upd.raise_for_status()
        return {
            "file_id": file_id,
            "folder_id": parent,
            "folder_name": day["name"],
            "name": name,
            "updated": True,
        }

    boundary = "=======kirs_ttn_upload======="
    meta = json.dumps(
        {"name": name, "parents": [parent], "mimeType": "application/pdf"},
        ensure_ascii=False,
    )
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{meta}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    create = session.post(
        DRIVE_UPLOAD,
        params={"uploadType": "multipart", "fields": "id,name"},
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        data=body,
        timeout=90,
    )
    create.raise_for_status()
    info = create.json() or {}
    return {
        "file_id": str(info.get("id") or ""),
        "folder_id": parent,
        "folder_name": day["name"],
        "name": name,
        "updated": False,
    }


def download_pdf_bytes(file_id: str) -> bytes:
    fid = str(file_id or "").strip()
    if not fid:
        raise ValueError("Немає file_id")
    session = _session()
    resp = session.get(
        f"{DRIVE_FILES}/{fid}",
        params={"alt": "media"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def decode_pdf_base64(raw: str) -> bytes:
    import base64

    text = str(raw or "").strip()
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    return base64.b64decode(text, validate=False)


def persist_order_ttn_pdf(
    storage: Any,
    order: dict[str, Any],
    *,
    pdf_bytes: bytes,
    source: str,
    filename: str = "",
) -> dict[str, Any] | None:
    """
    Зберегти PDF на Drive і записати метадані в payload замовлення.
    source: upload | np_print
    """
    if not pdf_bytes:
        return None
    if not root_folder_id():
        logger.warning(
            "TTN Drive skip: TTN_DRIVE_ROOT_FOLDER_ID не задано (order=%s)",
            order.get("order_number"),
        )
        return None
    order_number = str(order.get("order_number") or "")
    ttn = str(order.get("ttn_number") or (order.get("payload") or {}).get("ttn_number") or "")
    name = filename or _safe_filename(order_number, ttn or "label")
    try:
        uploaded = upload_pdf_bytes(pdf_bytes, filename=name)
    except Exception:
        logger.exception(
            "TTN Drive upload failed order=%s", order.get("order_number")
        )
        return None
    patch = {
        "ttn_pdf_drive_file_id": uploaded.get("file_id") or "",
        "ttn_pdf_drive_folder_id": uploaded.get("folder_id") or "",
        "ttn_pdf_drive_folder_name": uploaded.get("folder_name") or "",
        "ttn_pdf_drive_name": uploaded.get("name") or name,
        "ttn_pdf_drive_source": source,
        "ttn_pdf_drive_saved_at": datetime.now(KYIV).isoformat(timespec="seconds"),
    }
    return storage.merge_order_payload(int(order["id"]), patch)
