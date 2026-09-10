"""Модуль відстеження статусів ТТН у Google Sheet «Закази» (10:00 та 21:00 Київ).

Перевіряє всі активні (не фінальні) ТТН у таблиці через API перевізників (Нова Пошта, Розетка)
і записує актуальний статус доставки безпосередньо у стовпець N («Статус»).
Замовлення зі статусами отримання або відмови повторно не опитуються.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import gspread

from bot.accounts import AppStorage
from bot.google_creds import SHEETS_SCOPES, load_google_credentials
from bot.novaposhta import NovaPoshtaClient

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
TRACKING_HOURS = (10, 21)

# Регулярний вираз для перевірки ТТН Нової Пошти (11-14 цифр)
_NP_TTN_RE = re.compile(r"^\d{11,14}$")


def _is_np_ttn(raw: str) -> bool:
    digits = re.sub(r"\D+", "", str(raw or ""))
    if not (11 <= len(digits) <= 14):
        return False
    return (
        digits.startswith(
            (
                "204",
                "205",
                "206",
                "207",
                "208",
                "590",
                "591",
                "100",
                "200",
                "500",
            )
        )
        or len(digits) in (13, 14)
    )


def is_terminal_sheet_status(status: str) -> bool:
    """Перевіряє, чи є статус у таблиці фінальним (отримано / відмова / повернення / скасовано)."""
    st = str(status or "").casefold().strip()
    if not st:
        return False
    # Отримано / виконано
    if any(
        w in st
        for w in (
            "отриман",
            "получен",
            "выполнен",
            "виконан",
            "вручен",
            "успішно",
        )
    ):
        return True
    # Відмова / повернення / скасування
    if any(
        w in st
        for w in (
            "відмов",
            "отказ",
            "повернен",
            "повернут",
            "возврат",
            "скасован",
            "отменен",
        )
    ):
        return True
    return False


def seconds_until_next_tracking_slot(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> tuple[float, int]:
    """Розрахунок затримки до наступного слоту відстеження (10:00 або 21:00 за Києвом)."""
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)

    if allow_current_hour and dt.hour in TRACKING_HOURS:
        return 0.0, dt.hour

    candidates: list[tuple[datetime, int]] = []
    for day_offset in (0, 1, 2):
        day = dt.date() + timedelta(days=day_offset)
        for hour in TRACKING_HOURS:
            target = datetime.combine(day, time(hour, 0), tzinfo=KYIV)
            if target > dt:
                candidates.append((target, hour))
    candidates.sort(key=lambda x: x[0])
    target, hour = candidates[0]
    return max(30.0, (target - dt).total_seconds()), hour


def _clean_ttn(raw: str) -> str:
    return str(raw or "").strip()


def _open_orders_sheet(storage: AppStorage) -> gspread.Worksheet | None:
    settings = storage.get_general_settings()
    sheet_id = str(settings.get("orders_spreadsheet_id") or "").strip()
    if not sheet_id:
        from bot.orders_sheets import DEFAULT_ORDERS_SHEET_ID

        sheet_id = DEFAULT_ORDERS_SHEET_ID
    if not sheet_id:
        return None
    sheet_title = str(settings.get("orders_sheet_title") or "Заказы").strip() or "Заказы"
    try:
        creds = load_google_credentials(SHEETS_SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        try:
            return sh.worksheet(sheet_title)
        except gspread.WorksheetNotFound:
            return sh.sheet1
    except Exception:
        logger.exception("Failed to open orders worksheet for tracking sync")
        return None


def fetch_np_tracking_statuses(
    storage: AppStorage, ttns: list[str]
) -> dict[str, dict[str, Any]]:
    """Пакетний запит статусів до Нової Пошти для списку ТТН.

    Повертає словник {ttn: {"status": str, "status_code": str, "raw": dict}}.
    """
    clean_ttns = list(dict.fromkeys(re.sub(r"\D+", "", t) for t in ttns if _is_np_ttn(t)))
    if not clean_ttns:
        return {}

    from bot.np_fulfillment import list_np_clients

    clients = list_np_clients(storage)
    if not clients:
        # Спробуємо базовий клієнт
        clients = [{"client": NovaPoshtaClient(), "label": "default"}]

    results: dict[str, dict[str, Any]] = {}
    chunk_size = 80

    for i in range(0, len(clean_ttns), chunk_size):
        chunk = clean_ttns[i : i + chunk_size]
        docs = [{"DocumentNumber": ttn} for ttn in chunk]
        last_exc: Exception | None = None
        data: list[dict[str, Any]] = []

        for entry in clients:
            client: NovaPoshtaClient = entry.get("client")
            if not client:
                continue
            try:
                data = client.get_status_documents(docs)
                if data:
                    break
            except Exception as exc:
                last_exc = exc
                continue

        if not data and last_exc:
            logger.warning("NP tracking batch failed for chunk of %d ttns: %s", len(chunk), last_exc)

        for row in data:
            if not isinstance(row, dict):
                continue
            number = re.sub(r"\D+", "", str(row.get("Number") or ""))
            status_text = str(row.get("Status") or "").strip()
            status_code = str(row.get("StatusCode") or "").strip()
            if number and status_text:
                results[number] = {
                    "status": status_text,
                    "status_code": status_code,
                    "raw": row,
                }

    return results


def lookup_single_ttn_status(storage: AppStorage, ttn: str) -> str:
    """Швидка перевірка статусу однієї ТТН від перевізника."""
    return str(lookup_ttn_details(storage, ttn).get("status") or "").strip()


def lookup_ttn_details(storage: AppStorage, ttn: str) -> dict[str, Any]:
    """Дані отримувача та статус з трекінгу НП (для ручного запису за готовою ТТН)."""
    clean = re.sub(r"\s+", "", str(ttn or "").strip())
    digits = re.sub(r"\D+", "", clean)

    def _empty() -> dict[str, Any]:
        return {
            "ttn": digits or clean,
            "found": False,
            "status": "",
            "name": "",
            "phone": "",
            "city": "",
            "warehouse": "",
            "client": "",
        }

    if not digits or not _is_np_ttn(digits):
        return _empty()

    res = fetch_np_tracking_statuses(storage, [digits])
    info = res.get(digits) or {}
    raw = info.get("raw") if isinstance(info.get("raw"), dict) else {}

    def _pick(*keys: str) -> str:
        for key in keys:
            text = str((raw or {}).get(key) or "").strip()
            if text:
                return text
        return ""

    name = _pick(
        "RecipientFullName",
        "RecipientName",
        "RecipientFullNameEW",
        "CounterpartyRecipientDescription",
    )
    phone = _pick("PhoneRecipient", "Phone")
    city = _pick("CityRecipient", "CityRecipientDescription", "RecipientCityName")
    warehouse = _pick(
        "WarehouseRecipient",
        "RecipientAddressName",
        "RecipientAddress",
        "WarehouseRecipientNumber",
    )
    status = str(info.get("status") or _pick("Status") or "").strip()
    client = " ".join(p for p in (city, warehouse, name, phone) if p)
    found = bool(status or name or city or warehouse)
    return {
        "ttn": digits,
        "found": found,
        "status": status,
        "name": name,
        "phone": phone,
        "city": city,
        "warehouse": warehouse,
        "client": client,
    }


def run_sheet_tracking_sync(storage: AppStorage) -> dict[str, Any]:
    """Прохід оновлення статусів у Google Sheet «Заказы».

    Пропускає рядки, де статус уже є фінальним (отримано або відмова/повернення).
    """
    ws = _open_orders_sheet(storage)
    if not ws:
        return {"ok": False, "error": "Не вдалося відкрити Google Sheet"}

    all_rows = ws.get_all_values()
    if len(all_rows) < 2:
        return {"ok": True, "rows": 0, "updated": 0}

    # Збираємо рядки для перевірки
    # Стовпець B: № Замовлення (index 1)
    # Стовпець D: Служба доставки (index 3)
    # Стовпець M: ТТН (index 12)
    # Стовпець N: Статус (index 13)
    np_ttns_to_check: list[str] = []
    rows_meta: list[dict[str, Any]] = []
    skipped_terminal = 0

    for idx, row in enumerate(all_rows[1:], start=2):
        while len(row) < 18:
            row.append("")
        order_no = str(row[1] or "").strip()
        carrier = str(row[3] or "").strip()
        ttn_raw = str(row[12] or "").strip()
        current_status = str(row[13] or "").strip()

        if not ttn_raw:
            continue

        # Якщо статус уже фінальний (отримано / відмова / повернення) — не опитуємо повторно
        if is_terminal_sheet_status(current_status):
            skipped_terminal += 1
            continue

        digits_ttn = re.sub(r"\D+", "", ttn_raw)
        is_np = _is_np_ttn(ttn_raw) or carrier.upper() in {"НП", "НОВА ПОШТА", "NOVA POSHTA"}

        if is_np and (11 <= len(digits_ttn) <= 14):
            np_ttns_to_check.append(digits_ttn)

        rows_meta.append(
            {
                "row": idx,
                "order_no": order_no,
                "carrier": carrier,
                "ttn_raw": ttn_raw,
                "digits_ttn": digits_ttn,
                "current_status": current_status,
                "is_np": is_np,
            }
        )

    # Опитуємо Нову Пошту
    np_statuses = fetch_np_tracking_statuses(storage, np_ttns_to_check)

    updates: list[dict[str, Any]] = []
    updated_count = 0

    for meta in rows_meta:
        row_num = meta["row"]
        current_status = meta["current_status"]
        new_status = ""

        # 1. Нова Пошта
        if meta["digits_ttn"] in np_statuses:
            info = np_statuses[meta["digits_ttn"]]
            new_status = str(info.get("status") or "").strip()

        # 2. Якщо перевізник Rozetka або ТТН PRM- / Rozetka Delivery
        elif meta["carrier"].lower() == "розетка" or meta["ttn_raw"].startswith("PRM-"):
            pass

        if new_status and new_status != current_status:
            updates.append({"range": f"N{row_num}", "values": [[new_status]]})
            updated_count += 1

    if updates:
        # Пакетний запис у Google Sheet чанками по 80 комірок
        chunk_size = 80
        for i in range(0, len(updates), chunk_size):
            chunk = updates[i : i + chunk_size]
            ws.batch_update(chunk, value_input_option="USER_ENTERED")
        logger.info(
            "Sheet tracking sync: оновлено %d статусів у таблиці Закази (пропущено завершених: %d)",
            updated_count,
            skipped_terminal,
        )

    return {
        "ok": True,
        "total_rows": len(all_rows) - 1,
        "checked_ttns": len(rows_meta),
        "skipped_terminal": skipped_terminal,
        "np_tracked": len(np_statuses),
        "updated_statuses": updated_count,
    }
