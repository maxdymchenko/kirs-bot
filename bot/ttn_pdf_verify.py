"""Звірка номера ТТН/RMP у PDF-етикетці з номером у замовленні."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bot.accounts import AppStorage

logger = logging.getLogger(__name__)

_NP_TTN_RE = re.compile(r"(?<!\d)(\d{14})(?!\d)")
_RMP_RE = re.compile(r"(RMP-\d{6,20})", re.IGNORECASE)
_MAX_PDF_BYTES = 2_500_000


def decode_pdf_base64(raw: str) -> bytes:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("Порожній PDF")
    if "," in s and s.lower().startswith("data:"):
        s = s.split(",", 1)[1]
    s = re.sub(r"\s+", "", s)
    try:
        data = base64.b64decode(s, validate=False)
    except Exception as exc:
        raise ValueError("Некоректний PDF (base64)") from exc
    if len(data) > _MAX_PDF_BYTES:
        raise ValueError("PDF занадто великий (макс. ~2.5 МБ)")
    if not data.startswith(b"%PDF"):
        raise ValueError("Файл не схожий на PDF")
    return data


def normalize_waybill(value: str, carrier: str = "") -> str:
    raw = str(value or "").strip()
    carrier = str(carrier or "").strip().lower()
    if carrier == "rozetka" or raw.upper().startswith("RMP-"):
        m = _RMP_RE.search(raw.replace(" ", ""))
        return m.group(1).upper() if m else ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 14:
        return digits[:14] if len(digits) == 14 else digits[-14:]
    return digits


def extract_waybill_candidates(pdf_bytes: bytes) -> list[str]:
    """Усі знайдені в PDF номери НП (14 цифр) та Rozetka (RMP-…)."""
    texts: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                logger.debug("pypdf page extract failed", exc_info=True)
    except Exception:
        logger.debug("pypdf read failed", exc_info=True)

    try:
        texts.append(pdf_bytes.decode("latin-1", errors="ignore"))
    except Exception:
        pass

    blob = "\n".join(texts)
    found: list[str] = []
    seen: set[str] = set()
    for m in _RMP_RE.finditer(blob):
        val = m.group(1).upper()
        if val not in seen:
            seen.add(val)
            found.append(val)
    for m in _NP_TTN_RE.finditer(blob):
        val = m.group(1)
        if val not in seen:
            seen.add(val)
            found.append(val)
    return found


def verify_ttn_pdf(
    *,
    pdf_bytes: bytes,
    ttn_number: str,
    carrier: str = "",
) -> dict[str, Any]:
    """
    Повертає {ok, expected, found, message}.
    ok=False якщо номер не знайдено в PDF або не збігається.
    """
    expected = normalize_waybill(ttn_number, carrier)
    if not expected:
        return {
            "ok": False,
            "expected": "",
            "found": [],
            "message": "Вкажіть коректний номер накладної",
        }

    found = extract_waybill_candidates(pdf_bytes)
    if not found:
        return {
            "ok": False,
            "expected": expected,
            "found": [],
            "message": (
                "Не вдалося прочитати номер накладної з PDF. "
                "Прикріпіть оригінальну етикетку 100×100 (текст/вектор), не скан-фото."
            ),
        }

    carrier_l = str(carrier or "").strip().lower()
    if carrier_l == "rozetka" or expected.startswith("RMP-"):
        match = any(normalize_waybill(x, "rozetka") == expected for x in found)
    else:
        match = any(normalize_waybill(x, "nova_poshta") == expected for x in found)

    if not match:
        preview = ", ".join(found[:3])
        return {
            "ok": False,
            "expected": expected,
            "found": found,
            "message": (
                f"Номер у замовленні ({expected}) не збігається з номером у PDF "
                f"({preview}). Перевірте ТТН і файл етикетки."
            ),
        }

    return {
        "ok": True,
        "expected": expected,
        "found": found,
        "message": "OK",
    }


def verify_ttn_pdf_base64(
    *,
    pdf_b64: str,
    ttn_number: str,
    carrier: str = "",
) -> dict[str, Any]:
    try:
        pdf_bytes = decode_pdf_base64(pdf_b64)
    except ValueError as exc:
        return {
            "ok": False,
            "expected": normalize_waybill(ttn_number, carrier),
            "found": [],
            "message": str(exc),
        }
    return verify_ttn_pdf(
        pdf_bytes=pdf_bytes, ttn_number=ttn_number, carrier=carrier
    )


def apply_ttn_pdf_check(
    storage: "AppStorage",
    order: dict[str, Any],
    *,
    pdf_b64: str,
    ttn_number: str | None = None,
    carrier: str | None = None,
) -> dict[str, Any]:
    """
    Звірити PDF з номером, записати результат у payload.
    При розбіжності — hold (не в упаковку/sheets), поки не виправлять.
    """
    from datetime import datetime, timezone

    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    number = str(ttn_number if ttn_number is not None else order.get("ttn_number") or "")
    carr = str(
        carrier
        if carrier is not None
        else (payload.get("own_ttn_carrier") or "")
    )
    check = verify_ttn_pdf_base64(pdf_b64=pdf_b64, ttn_number=number, carrier=carr)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ok = bool(check.get("ok"))
    patch = {
        "ttn_pdf_ok": ok,
        "ttn_pdf_hold": not ok,
        "ttn_pdf_check_message": str(check.get("message") or ""),
        "ttn_pdf_expected": str(check.get("expected") or ""),
        "ttn_pdf_found": list(check.get("found") or [])[:5],
        "ttn_pdf_checked_at": now,
    }
    saved = storage.merge_order_payload(int(order["id"]), patch)
    if ok:
        storage.update_order_flags(int(order["id"]), sheets_sync_status="pending")
    else:
        storage.update_order_flags(int(order["id"]), sheets_sync_status="hold_pdf")
    return {
        "ok": ok,
        "check": check,
        "order": storage.get_order(int(order["id"])) or saved or order,
    }


def format_ttn_pdf_mismatch_message(order: dict[str, Any], check: dict[str, Any]) -> str:
    order_no = str(order.get("order_number") or "")
    expected = str(check.get("expected") or order.get("ttn_number") or "—")
    found = check.get("found") or []
    found_s = ", ".join(str(x) for x in found[:3]) if found else "не знайдено в PDF"
    detail = str(check.get("message") or "")
    return (
        f"⚠️ Перевірте накладну · {order_no}\n\n"
        f"Номер у замовленні: {expected}\n"
        f"У PDF: {found_s}\n\n"
        f"{detail}\n\n"
        "Виправте номер ТТН або прикріпіть правильний PDF у «Історії». "
        "Поки це не виправлено, замовлення не піде кладовщику на упаковку."
    )

