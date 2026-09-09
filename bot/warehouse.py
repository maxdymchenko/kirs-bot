"""Черга пакування / відправлення для комірника (warehouse)."""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime
from typing import Any

from bot.accounts import AppStorage
from bot.np_fulfillment import AWAITING_SHIPMENT_STATUSES, SHIPPED_OR_FINAL_STATUSES

logger = logging.getLogger(__name__)

STAGE_PACKING = "packing"
STAGE_READY = "ready_to_ship"
SHEET_ID_PREFIX = "sheet:"
SHEET_STAGE_KEY = "sheet_warehouse_stages"

# Власна ТТН дроппера теж пакується на складі, поки НП ще не забрала.
PACKABLE_TTN_STATUSES = frozenset(AWAITING_SHIPMENT_STATUSES | {"provided"})

_MARKET_SOURCE_MARKERS = (
    "пром",
    "prom",
    "rozetka",
    "розет",
    "kasta",
    "каста",
    "телефон",
    "olx",
    "instagram",
    "інстаграм",
    "инстаграм",
    "інше",
    "viber",
)
_LEFT_WAREHOUSE_STATUS = (
    "в дорозі",
    "у дорозі",
    "в дороге",
    "на відділен",
    "на отделен",
    "у відділен",
    "прибув на",
    "прибыл на",
    "передано перевізнику",
    "прямує до",
    "видано одержувачу",
)


def order_warehouse_stage(order: dict[str, Any]) -> str:
    raw = str(order.get("warehouse_stage") or "").strip()
    if raw in {STAGE_PACKING, STAGE_READY}:
        return raw
    payload = order.get("payload") or {}
    raw2 = str(payload.get("warehouse_stage") or "").strip()
    if raw2 in {STAGE_PACKING, STAGE_READY}:
        return raw2
    return STAGE_PACKING


def is_packable_order(order: dict[str, Any]) -> bool:
    if str(order.get("status") or "") == "cancelled":
        return False
    if str(order.get("sheets_sync_status") or "") == "hold_pdf":
        return False
    payload = order.get("payload") or {}
    if payload.get("ttn_pdf_hold") is True:
        return False
    ttn = str(order.get("ttn_status") or "none").strip() or "none"
    if ttn in SHIPPED_OR_FINAL_STATUSES:
        return False
    if ttn not in PACKABLE_TTN_STATUSES:
        return False
    return True


def is_sheet_queue_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    if payload.get("sheet_order"):
        return True
    return str(order.get("id") or "").startswith(SHEET_ID_PREFIX)


def sheet_order_id(order_no: str) -> str:
    return f"{SHEET_ID_PREFIX}{str(order_no or '').strip()}"


def parse_sheet_order_id(order_id: Any) -> str | None:
    raw = str(order_id or "").strip()
    if raw.startswith(SHEET_ID_PREFIX):
        no = raw[len(SHEET_ID_PREFIX) :].strip()
        return no or None
    return None


def _clean_location(raw: Any) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    folded = text.casefold()
    if folded in {"-", "—", "–", "н/д", "нет", "немає", "null", "none"}:
        return ""
    if folded.startswith("уточнен"):
        return ""
    return text


def _is_market_or_manual_source(source: str, order_no: str = "") -> bool:
    text = str(source or "").casefold()
    no = str(order_no or "").strip().upper()
    if no.startswith("TEL-"):
        return True
    if not text:
        return False
    return any(marker in text for marker in _MARKET_SOURCE_MARKERS)


def _is_sheet_row_still_packing(status: str) -> bool:
    from bot.sheet_tracking import is_terminal_sheet_status

    raw = str(status or "").strip()
    if is_terminal_sheet_status(raw):
        return False
    folded = raw.casefold()
    return not any(word in folded for word in _LEFT_WAREHOUSE_STATUS)


def _sheet_qty(raw: Any) -> int:
    text = str(raw or "").strip().replace(" ", "").replace(",", ".")
    try:
        n = int(float(text)) if text else 1
    except (TypeError, ValueError):
        n = 1
    return max(1, n)


def _sheet_created_at(raw: Any, row_idx: int) -> str:
    text = str(raw or "").strip()
    for fmt, size in (
        ("%d.%m.%Y %H:%M:%S", 19),
        ("%d.%m.%Y %H:%M", 16),
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%d.%m.%Y", 10),
        ("%Y-%m-%d", 10),
    ):
        chunk = text[:size]
        try:
            return datetime.strptime(chunk, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return f"1970-01-01 {max(0, int(row_idx)):08d}"


def _looks_like_np_ttn(ttn: str) -> bool:
    digits = "".join(ch for ch in str(ttn or "") if ch.isdigit())
    return len(digits) >= 11


def _load_sheet_stages(storage: AppStorage) -> dict[str, str]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SHEET_STAGE_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in data.items():
        no = str(key or "").strip()
        stage = str(val or "").strip()
        if no and stage in {STAGE_PACKING, STAGE_READY}:
            out[no] = stage
    return out


def _save_sheet_stages(storage: AppStorage, stages: dict[str, str]) -> None:
    from bot.accounts import _now

    cleaned = {
        str(k).strip(): str(v)
        for k, v in (stages or {}).items()
        if str(k).strip() and str(v) in {STAGE_PACKING, STAGE_READY}
    }
    payload = json.dumps(cleaned, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SHEET_STAGE_KEY, payload, _now()),
        )
        conn.commit()


def set_sheet_warehouse_stage(
    storage: AppStorage, order_no: str, stage: str
) -> None:
    no = str(order_no or "").strip()
    stage_key = STAGE_READY if stage == STAGE_READY else STAGE_PACKING
    if not no:
        raise ValueError("Немає номера замовлення")
    stages = _load_sheet_stages(storage)
    stages[no] = stage_key
    _save_sheet_stages(storage, stages)


def _sheet_money(raw: Any) -> float:
    text = str(raw or "").strip().replace(" ", "").replace(",", ".")
    if not text:
        return 0.0
    try:
        return max(0.0, float(text))
    except (TypeError, ValueError):
        return 0.0


def _phone_from_client(text: str) -> str:
    digits = re.sub(r"\D+", "", str(text or ""))
    if len(digits) >= 10:
        return digits[-12:] if len(digits) > 12 else digits
    return ""


def _sheet_status_to_ttn(status: str, ttn: str) -> str:
    from bot.sheet_tracking import is_terminal_sheet_status

    raw = str(status or "").strip()
    folded = raw.casefold()
    has_ttn = bool(str(ttn or "").strip())
    if is_terminal_sheet_status(raw):
        if any(
            w in folded
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
            if "скасован" in folded or "отменен" in folded:
                return "cancelled"
            return "returned"
        return "received"
    if any(word in folded for word in _LEFT_WAREHOUSE_STATUS):
        if any(
            w in folded
            for w in ("відділен", "отделен", "прибув", "прибыл")
        ):
            return "at_warehouse"
        return "in_transit"
    if "помилка" in folded or "ошибка" in folded:
        return "create_error"
    if has_ttn:
        return "created"
    return "none"


def _load_sheet_market_groups(
    storage: AppStorage, *, packing_only: bool
) -> dict[str, list[dict[str, Any]]]:
    try:
        from bot.orders_sheets import _open_orders_worksheet

        ws = _open_orders_worksheet(storage)
        rows = ws.get_all_values()
    except Exception:
        logger.exception("warehouse: failed to read marketplace rows from sheet")
        return {}

    groups: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(rows[1:], start=2):
        while len(row) < 18:
            row.append("")
        order_no = str(row[1] or "").strip()
        source = str(row[10] or "").strip()
        if not order_no or not _is_market_or_manual_source(source, order_no):
            continue
        status = str(row[13] or "").strip()
        if packing_only and not _is_sheet_row_still_packing(status):
            continue
        groups.setdefault(order_no, []).append(
            {
                "row_idx": idx,
                "created_raw": row[0],
                "payment": str(row[2] or "").strip(),
                "name": str(row[4] or "").strip(),
                "code": str(row[5] or "").strip(),
                "color": str(row[6] or "").strip(),
                "qty": _sheet_qty(row[7]),
                "retail": _sheet_money(row[8]),
                "source": source,
                "client": str(row[11] or "").strip(),
                "ttn": str(row[12] or "").strip(),
                "status": status,
                "location": _clean_location(row[17] if len(row) > 17 else ""),
            }
        )
    return groups


def _sheet_order_from_lines(
    order_no: str,
    lines: list[dict[str, Any]],
    *,
    stages: dict[str, str] | None = None,
    for_history: bool = False,
) -> dict[str, Any]:
    lines = sorted(lines, key=lambda x: int(x.get("row_idx") or 0))
    latest = lines[-1]
    ttn = next((str(x.get("ttn") or "").strip() for x in lines if x.get("ttn")), "")
    sources: list[str] = []
    for line in lines:
        src = str(line.get("source") or "").strip()
        if src and src not in sources:
            sources.append(src)
    client = next(
        (str(x.get("client") or "").strip() for x in lines if x.get("client")),
        "",
    )
    payment = next(
        (str(x.get("payment") or "").strip() for x in lines if x.get("payment")),
        "",
    )
    created_at = _sheet_created_at(latest.get("created_raw"), latest.get("row_idx") or 0)
    source_label = " · ".join(sources)
    total = round(sum(float(x.get("retail") or 0) * int(x.get("qty") or 1) for x in lines), 2)
    if for_history:
        ttn_status = _sheet_status_to_ttn(str(latest.get("status") or ""), ttn)
        status = "cancelled" if ttn_status == "cancelled" else "accepted"
    else:
        ttn_status = "created" if ttn else "none"
        status = "new"
    stage = (stages or {}).get(order_no) or STAGE_PACKING
    if stage not in {STAGE_PACKING, STAGE_READY}:
        stage = STAGE_PACKING
    return {
        "id": sheet_order_id(order_no),
        "order_number": order_no,
        "ttn_number": ttn,
        "own_ttn": False,
        "created_at": created_at,
        "warehouse_stage": stage,
        "status": status,
        "ttn_status": ttn_status,
        "payment_method": payment,
        "total": total,
        "prepay": 0,
        "payload": {
            "sheet_order": True,
            "market_source": source_label,
            "warehouse_stage": stage,
            "ttn_number": ttn,
            "comment": source_label,
            "recipient": {
                "first_name": client,
                "last_name": "",
                "phone": _phone_from_client(client),
            },
            "payment": {"method": payment},
            "cart": [
                {
                    "name": str(line.get("name") or ""),
                    "code": str(line.get("code") or ""),
                    "color": str(line.get("color") or ""),
                    "qty": int(line.get("qty") or 1),
                    "location": str(line.get("location") or ""),
                    "source": str(line.get("source") or ""),
                    "drop_price": str(line.get("retail") or ""),
                }
                for line in lines
            ],
        },
    }


def list_sheet_warehouse_orders(storage: AppStorage) -> list[dict[str, Any]]:
    """Prom / Rozetka / ручні з листа «Заказы», які ще на складі (1 картка = 1 №)."""
    groups = _load_sheet_market_groups(storage, packing_only=True)
    stages = _load_sheet_stages(storage)
    return [
        _sheet_order_from_lines(order_no, lines, stages=stages, for_history=False)
        for order_no, lines in groups.items()
    ]


def list_sheet_history_orders(storage: AppStorage) -> list[dict[str, Any]]:
    """Усі Prom / Rozetka / ручні з листа — для історії кабінету власника."""
    groups = _load_sheet_market_groups(storage, packing_only=False)
    stages = _load_sheet_stages(storage)
    out = [
        _sheet_order_from_lines(order_no, lines, stages=stages, for_history=True)
        for order_no, lines in groups.items()
    ]
    out.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return out


def list_owner_form_history(
    storage: AppStorage,
    *,
    owner_chat_id: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Замовлення Mini App власника (якщо є картка дроппера) + Prom/Rozetka/ручні з листа."""
    items: list[dict[str, Any]] = []
    seen_nos: set[str] = set()
    dropper = storage.get_dropper_by_chat(str(owner_chat_id or "").strip()) if owner_chat_id else None
    if dropper:
        sqlite_items = storage.list_orders_for_dropper(dropper.id, limit=limit)
        items.extend(sqlite_items)
        for order in sqlite_items:
            no = str(order.get("order_number") or "").strip()
            if no:
                seen_nos.add(no)
    for order in list_sheet_history_orders(storage):
        no = str(order.get("order_number") or "").strip()
        if no and no in seen_nos:
            continue
        items.append(order)
        if no:
            seen_nos.add(no)
    items.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def get_sheet_warehouse_order(
    storage: AppStorage, order_no: str
) -> dict[str, Any] | None:
    no = str(order_no or "").strip()
    if not no:
        return None
    for order in list_sheet_warehouse_orders(storage):
        if str(order.get("order_number") or "").strip() == no:
            return order
    return None


def list_warehouse_queue(
    storage: AppStorage,
    *,
    stage: str,
    limit: int = 300,
) -> list[dict[str, Any]]:
    stage_key = STAGE_READY if stage == STAGE_READY else STAGE_PACKING
    items = storage.list_orders_for_warehouse(limit=limit)
    out: list[dict[str, Any]] = []
    seen_nos: set[str] = set()
    for order in items:
        if not is_packable_order(order):
            continue
        if order_warehouse_stage(order) != stage_key:
            continue
        out.append(order)
        no = str(order.get("order_number") or "").strip()
        if no:
            seen_nos.add(no)
    for order in list_sheet_warehouse_orders(storage):
        no = str(order.get("order_number") or "").strip()
        if no and no in seen_nos:
            continue
        if order_warehouse_stage(order) != stage_key:
            continue
        out.append(order)
        if no:
            seen_nos.add(no)
    # новіші зверху (created_at DESC уже з SQL, але підстрахуємо)
    out.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return out


def mark_order_ready_to_ship(
    storage: AppStorage,
    order_id: int | str,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    sheet_no = parse_sheet_order_id(order_id)
    if sheet_no:
        order = get_sheet_warehouse_order(storage, sheet_no)
        if not order:
            raise ValueError("Замовлення не знайдено")
        if order_warehouse_stage(order) == STAGE_READY:
            return order
        set_sheet_warehouse_stage(storage, sheet_no, STAGE_READY)
        order["warehouse_stage"] = STAGE_READY
        payload = dict(order.get("payload") or {})
        payload["warehouse_stage"] = STAGE_READY
        payload["warehouse_ready_by"] = str(actor_user_id or "")
        order["payload"] = payload
        return order
    try:
        sqlite_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Замовлення не знайдено") from exc
    order = storage.get_order(sqlite_id)
    if not order:
        raise ValueError("Замовлення не знайдено")
    if not is_packable_order(order):
        raise ValueError("Замовлення вже не в черзі на пакування")
    if order_warehouse_stage(order) == STAGE_READY:
        return order
    storage.set_order_warehouse_stage(sqlite_id, STAGE_READY)
    storage.merge_order_payload(
        sqlite_id,
        {
            "warehouse_stage": STAGE_READY,
            "warehouse_ready_by": str(actor_user_id or ""),
        },
    )
    storage.add_order_change(
        order_id=sqlite_id,
        order_number=str(order.get("order_number") or ""),
        actor_role="warehouse",
        actor_user_id=str(actor_user_id or ""),
        actor_label="Комірник",
        change_type="status",
        summary="Переміщено на відправлення (упаковано)",
        diff=[
            {
                "field": "warehouse_stage",
                "old": STAGE_PACKING,
                "new": STAGE_READY,
            }
        ],
    )
    return storage.get_order(sqlite_id) or order


def mark_order_back_to_packing(
    storage: AppStorage,
    order_id: int | str,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    sheet_no = parse_sheet_order_id(order_id)
    if sheet_no:
        order = get_sheet_warehouse_order(storage, sheet_no)
        if not order:
            raise ValueError("Замовлення не знайдено")
        set_sheet_warehouse_stage(storage, sheet_no, STAGE_PACKING)
        order["warehouse_stage"] = STAGE_PACKING
        payload = dict(order.get("payload") or {})
        payload["warehouse_stage"] = STAGE_PACKING
        order["payload"] = payload
        return order
    try:
        sqlite_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Замовлення не знайдено") from exc
    order = storage.get_order(sqlite_id)
    if not order:
        raise ValueError("Замовлення не знайдено")
    storage.set_order_warehouse_stage(sqlite_id, STAGE_PACKING)
    storage.merge_order_payload(
        sqlite_id,
        {"warehouse_stage": STAGE_PACKING},
    )
    storage.add_order_change(
        order_id=sqlite_id,
        order_number=str(order.get("order_number") or ""),
        actor_role="warehouse",
        actor_user_id=str(actor_user_id or ""),
        actor_label="Комірник",
        change_type="status",
        summary="Повернено на пакування",
        diff=[
            {
                "field": "warehouse_stage",
                "old": STAGE_READY,
                "new": STAGE_PACKING,
            }
        ],
    )
    return storage.get_order(sqlite_id) or order


def order_has_ttn_pdf(order: dict[str, Any]) -> bool:
    payload = order.get("payload") or {}
    if payload.get("sheet_order"):
        ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
        return _looks_like_np_ttn(ttn)
    return bool(
        payload.get("ttn_pdf_local_path")
        or payload.get("ttn_pdf_local_abs")
        or payload.get("ttn_pdf_drive_file_id")
    )


def _download_np_label_pdf(storage: AppStorage, order: dict[str, Any]) -> bytes:
    from bot.np_fulfillment import list_np_clients

    payload = order.get("payload") or {}
    doc_ref = str(payload.get("np_document_ref") or "").strip()
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    if not doc_ref and not ttn:
        raise ValueError(f"{order.get('order_number')}: немає Ref/ТТН для друку")

    clients = list_np_clients(storage)
    if not clients:
        raise ValueError("Немає API-ключа Нової Пошти для друку етикетки")

    last_err: Exception | None = None
    for label, client, _is_primary in clients:
        try:
            key = doc_ref or ttn
            pdf_bytes = client.download_marking_pdf(key)
            if pdf_bytes:
                return pdf_bytes
        except Exception as exc:
            last_err = exc
            logger.warning(
                "NP label download via «%s» failed order=%s: %s",
                label,
                order.get("order_number"),
                exc,
            )
    raise ValueError(
        f"{order.get('order_number')}: не вдалося завантажити PDF з НП"
        + (f" ({last_err})" if last_err else "")
    ) from last_err


def ensure_order_ttn_pdf(storage: AppStorage, order: dict[str, Any]) -> dict[str, Any]:
    """
    Якщо локального PDF немає — спробувати завантажити етикетку з НП
    (для замовлень, створених ключем власника).
    """
    from bot.ttn_drive import persist_order_ttn_pdf
    from bot.ttn_store import read_pdf_bytes

    payload = order.get("payload") or {}
    if payload.get("sheet_order"):
        if payload.get("_label_pdf_bytes"):
            return order
        pdf_bytes = _download_np_label_pdf(storage, order)
        payload = dict(payload)
        payload["_label_pdf_bytes"] = pdf_bytes
        order["payload"] = payload
        return order

    local = str(
        payload.get("ttn_pdf_local_path") or payload.get("ttn_pdf_local_abs") or ""
    ).strip()
    if local:
        try:
            read_pdf_bytes(local)
            return order
        except Exception:
            logger.info(
                "TTN local PDF missing for %s — try NP re-download",
                order.get("order_number"),
            )

    if payload.get("ttn_pdf_drive_file_id"):
        return order

    if order.get("own_ttn"):
        raise ValueError(
            f"{order.get('order_number')}: власна ТТН без завантаженого PDF"
        )

    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    pdf_bytes = _download_np_label_pdf(storage, order)
    saved = persist_order_ttn_pdf(
        storage,
        order,
        pdf_bytes=pdf_bytes,
        source="np_print_backfill",
        filename=f"{order.get('order_number')}_{ttn or 'label'}.pdf",
    )
    return saved or storage.get_order(int(order["id"])) or order


def merge_ready_ttn_pdfs(storage: AppStorage, orders: list[dict[str, Any]]) -> bytes:
    """Злити PDF накладних: 1 файл = 1+ листів, кожна накладна з нової сторінки."""
    from pypdf import PdfReader, PdfWriter

    from bot.ttn_drive import download_pdf_bytes
    from bot.ttn_store import read_pdf_bytes

    writer = PdfWriter()
    used = 0
    errors: list[str] = []
    for order in orders:
        try:
            order = ensure_order_ttn_pdf(storage, order)
        except Exception as exc:
            errors.append(str(exc))
            continue
        payload = order.get("payload") or {}
        local = str(
            payload.get("ttn_pdf_local_path")
            or payload.get("ttn_pdf_local_abs")
            or ""
        ).strip()
        file_id = str(payload.get("ttn_pdf_drive_file_id") or "").strip()
        mem = payload.get("_label_pdf_bytes")
        try:
            if isinstance(mem, (bytes, bytearray)) and mem:
                raw = bytes(mem)
            elif local:
                raw = read_pdf_bytes(local)
            elif file_id:
                raw = download_pdf_bytes(file_id)
            else:
                errors.append(str(order.get("order_number") or order.get("id")))
                continue
            reader = PdfReader(io.BytesIO(raw))
            for page in reader.pages:
                writer.add_page(page)
            used += 1
        except Exception as exc:
            logger.exception(
                "merge pdf failed order=%s", order.get("order_number")
            )
            errors.append(f"{order.get('order_number')}: {exc}")
    if used == 0:
        raise ValueError(
            "Немає PDF накладних для злиття. "
            + (", ".join(errors[:5]) if errors else "Завантажте/створіть ТТН ще раз.")
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
