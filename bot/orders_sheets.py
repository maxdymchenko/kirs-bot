"""Дзеркало замовлень у Google Sheet «Заказы» (18 колонок).

SQLite лишається джерелом правди; лист — для людей (склад / облік).
1 позиція кошика = 1 рядок. Баланс у Sheet не читаємо.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import gspread

from bot.accounts import AppStorage
from bot.google_creds import SHEETS_SCOPES, load_google_credentials

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")

ORDER_SHEET_HEADERS = [
    "Дата",
    "№ Заказа",
    "Оплата",
    "Служба доставки",
    "Название товара",
    "Код",
    "Цвет/модель",
    "Кол-во",
    "Цена продажи, грн",
    "Дроп цена, грн",
    "Источник заказа",
    "Данные клиента",
    "ТТН",
    "Статус",
    "Примечание",
    "Чек",
    "Рассчет с дроппером",
    "Расположение товара на складе",
]

# Колонки 1-based для точкових update
COL_DATE = 1
COL_ORDER_NO = 2
COL_TTN = 13
COL_STATUS = 14
COL_NOTE = 15
COL_RECEIPT = 16
COL_SETTLEMENT = 17
COL_LOCATION = 18

TTN_STATUS_LABELS = {
    "none": "немає ТТН",
    "pending_create": "очікує створення ТТН",
    "create_error": "помилка створення ТТН",
    "created": "ТТН створено",
    "provided": "ТТН надано",
    "in_transit": "в дорозі",
    "at_warehouse": "на відділенні",
    "received": "отримано",
    "refused": "відмова",
    "returned": "повернення",
    "return_at_warehouse": "повернення на складі",
    "cancelled": "скасовано",
    "failed": "помилка",
}


def _fmt_money(value: Any) -> str:
    """Суми для Sheet: десятковий роздільник — кома (напр. 510,23)."""
    try:
        n = float(str(value or "").replace(" ", "").replace(",", ".") or 0)
    except (TypeError, ValueError):
        return ""
    if abs(n) < 1e-9:
        return ""
    # завжди 2 знаки після коми — як у зразку листа (660,00)
    return f"{n:.2f}".replace(".", ",")


def _norm_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def sheet_status_label(order: dict[str, Any]) -> str:
    if str(order.get("status") or "") == "cancelled":
        return "скасовано"
    payload = order.get("payload") or {}
    ret = payload.get("dropper_return") if isinstance(payload.get("dropper_return"), dict) else None
    if ret and str(ret.get("status") or "") == "accepted":
        return "повернення підтверджено"
    if ret and str(ret.get("status") or ""):
        st = str(ret.get("status") or "")
        if st == "awaiting_receipt":
            return "повернення: очікує отримання"
        if st == "awaiting_confirm":
            return "повернення: очікує підтвердження"
    ttn = str(order.get("ttn_status") or "").strip()
    return TTN_STATUS_LABELS.get(ttn, ttn or "—")


def sheet_payment_label(order: dict[str, Any]) -> str:
    method = str(order.get("payment_method") or "").strip().lower()
    prepay = float(order.get("prepay") or 0)
    mapping = {
        "balance": "БАЛАНС",
        "requisites": "РЕКВІЗИТИ",
        "cod": "НАЛОЖКА",
    }
    base = mapping.get(method, method.upper() or "—")
    if method == "cod" and prepay > 0:
        return f"{base} + передплата {_fmt_money(prepay)}"
    if method == "requisites" and prepay > 0:
        return f"{base} {_fmt_money(prepay)}"
    return base


def sheet_carrier_label(order: dict[str, Any]) -> str:
    payload = order.get("payload") or {}
    if order.get("own_ttn") or payload.get("own_ttn"):
        carrier = str(payload.get("own_ttn_carrier") or "").strip().lower()
        if carrier == "rozetka":
            return "Rozetka"
        if carrier:
            return carrier
        return "власна ТТН"
    return "НП"


def sheet_client_line(order: dict[str, Any]) -> str:
    payload = order.get("payload") or {}
    recipient = payload.get("recipient") or {}
    delivery = payload.get("delivery") or {}
    name = " ".join(
        x
        for x in (
            recipient.get("last_name"),
            recipient.get("first_name"),
            recipient.get("patronymic"),
        )
        if str(x or "").strip()
    ).strip()
    phone = str(recipient.get("phone") or "").strip()
    city = str(delivery.get("city") or "").strip()
    if str(delivery.get("method") or "") in {"np_courier", "courier"}:
        addr = " ".join(
            x
            for x in (
                delivery.get("street"),
                delivery.get("house"),
                f"кв.{delivery['apartment']}" if delivery.get("apartment") else "",
            )
            if str(x or "").strip()
        ).strip()
        place = f"{city} {addr}".strip()
    else:
        wh = str(delivery.get("warehouse") or "").strip()
        place = f"{city} {wh}".strip()
    parts = [p for p in (place, name, phone) if p]
    return " ".join(parts)


def sheet_note(order: dict[str, Any]) -> str:
    payload = order.get("payload") or {}
    bits: list[str] = []
    comment = str(payload.get("comment") or "").strip()
    if comment:
        bits.append(comment)
    if order.get("own_ttn") or payload.get("own_ttn"):
        bits.append("власна ТТН")
    if payload.get("ttn_pdf_hold"):
        bits.append("hold PDF")
    return " · ".join(bits)


def sheet_receipt_label(order: dict[str, Any]) -> str:
    payload = order.get("payload") or {}
    payment = payload.get("payment") or {}
    name = str(payment.get("receipt_name") or "").strip()
    if name:
        return name
    return ""


def sheet_settlement_label(storage: AppStorage, order: dict[str, Any]) -> str:
    if str(order.get("status") or "") == "cancelled":
        return "—"
    payload = order.get("payload") or {}
    if payload.get("return_settled"):
        notes = []
        if payload.get("return_goods_credited"):
            amt = _fmt_money(payload.get("return_goods_amount"))
            notes.append(f"повернення товару +{amt}" if amt else "повернення товару")
        return "; ".join(notes) if notes else "повернення"
    order_no = str(order.get("order_number") or "")
    parts: list[str] = []
    if payload.get("goods_debited"):
        amt = _fmt_money(payload.get("goods_debit_amount") or order.get("total"))
        parts.append(f"списано дроп {amt}".strip() if amt else "списано дроп")
    if payload.get("profit_credited"):
        p = _fmt_money(payload.get("profit_amount"))
        parts.append(f"прибуток +{p}" if p else "прибуток")
    else:
        dropper_id = int(order.get("dropper_id") or 0)
        if dropper_id and order_no:
            for row in storage.list_ledger(
                dropper_id, entry_type="cod_profit_credit", limit=200
            ):
                if str(row.get("related_order_id") or "") == order_no:
                    profit = float(row.get("amount") or 0)
                    if profit > 0:
                        p = _fmt_money(profit)
                        parts.append(f"прибуток +{p}" if p else "прибуток")
                    break
    if payload.get("prepay_overage_posted"):
        parts.append("передплата понад дроп")
    if parts:
        return "; ".join(parts)
    ttn = str(order.get("ttn_status") or "")
    if ttn in {"received", "returned", "return_at_warehouse"}:
        return "очікує разноски"
    return "очікує"


def _lookup_variant_meta(catalog: Any, code: str, color: str) -> tuple[str, str]:
    """Повертає (retail_price, location)."""
    if catalog is None:
        return "", ""
    try:
        variants = catalog.all_variants()
    except Exception:
        logger.exception("catalog all_variants failed for sheet enrich")
        return "", ""
    code_n = _norm_text(code)
    color_n = _norm_text(color)
    matches = []
    for v in variants:
        if _norm_text(getattr(v, "code", "")) != code_n and str(
            getattr(v, "code", "") or ""
        ).lstrip("0") != str(code or "").lstrip("0"):
            # soft: normalize leading zeros via catalog helper if available
            try:
                if not catalog._codes_equal(getattr(v, "code", ""), code):
                    continue
            except Exception:
                continue
        matches.append(v)
    if not matches:
        return "", ""
    if color_n:
        by_color = [v for v in matches if _norm_text(getattr(v, "color", "")) == color_n]
        if by_color:
            matches = by_color
    v = matches[0]
    return str(getattr(v, "retail_price", "") or ""), str(getattr(v, "location", "") or "")


def build_sheet_rows(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    catalog: Any = None,
    dropper: Any = None,
) -> list[list[Any]]:
    payload = order.get("payload") or {}
    cart = payload.get("cart") if isinstance(payload.get("cart"), list) else []
    if not cart:
        cart = [
            {
                "name": "",
                "code": "",
                "color": "",
                "qty": 1,
                "drop_price": order.get("total") or "",
            }
        ]

    if dropper is None and order.get("dropper_id"):
        dropper = storage.get_dropper_by_id(int(order["dropper_id"]))

    source = ""
    if dropper is not None:
        source = str(getattr(dropper, "company_name", "") or "").strip()

    created = str(order.get("created_at") or "")
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KYIV)
        date_s = dt.astimezone(KYIV).strftime("%d.%m.%Y")
    except ValueError:
        date_s = created[:10] if created else datetime.now(KYIV).strftime("%d.%m.%Y")

    payment = sheet_payment_label(order)
    carrier = sheet_carrier_label(order)
    client = sheet_client_line(order)
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    status = sheet_status_label(order)
    note = sheet_note(order)
    receipt = sheet_receipt_label(order)
    settlement = sheet_settlement_label(storage, order)
    order_no = str(order.get("order_number") or "")

    rows: list[list[Any]] = []
    for item in cart:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        color = str(item.get("color") or "").strip()
        retail = str(item.get("retail_price") or "").strip()
        location = str(item.get("location") or "").strip()
        if not retail or not location:
            r2, loc2 = _lookup_variant_meta(catalog, code, color)
            retail = retail or r2
            location = location or loc2
        qty = max(1, int(item.get("qty") or 1))
        drop = _fmt_money(item.get("drop_price"))
        retail_s = _fmt_money(retail) if retail else str(retail or "")
        rows.append(
            [
                date_s,
                order_no,
                payment,
                carrier,
                str(item.get("name") or "").strip(),
                code,
                color,
                qty,
                retail_s,
                drop,
                source,
                client,
                ttn,
                status,
                note,
                receipt,
                settlement,
                location,
            ]
        )
    return rows


def _open_orders_worksheet(storage: AppStorage) -> gspread.Worksheet:
    settings = storage.get_general_settings()
    sheet_id = str(settings.get("orders_spreadsheet_id") or "").strip()
    title = str(settings.get("orders_sheet_title") or "Заказы").strip() or "Заказы"
    if not sheet_id:
        raise RuntimeError("orders_spreadsheet_id не задано в налаштуваннях")
    client = gspread.authorize(load_google_credentials(SHEETS_SCOPES))
    sh = client.open_by_key(sheet_id)
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.sheet1


def _parse_updated_range_start_row(updated_range: str) -> int | None:
    # 'Заказы'!A5:R7 or A5:R7
    text = str(updated_range or "")
    match = re.search(r"![A-Z]+(\d+)", text) or re.search(r"^([A-Z]+)(\d+)", text)
    if not match:
        match = re.search(r"(\d+)", text)
        if not match:
            return None
        return int(match.group(1))
    # group with row
    for g in match.groups():
        if g and str(g).isdigit():
            return int(g)
    return None


def find_sheet_rows_by_order_number(
    ws: gspread.Worksheet, order_number: str
) -> list[int]:
    order_number = str(order_number or "").strip()
    if not order_number:
        return []
    col = ws.col_values(COL_ORDER_NO)
    out: list[int] = []
    for idx, value in enumerate(col):
        if idx == 0:
            continue  # header
        if str(value or "").strip() == order_number:
            out.append(idx + 1)
    return out


def _save_sheet_meta(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    sheet_rows: list[dict[str, Any]],
    sync_status: str,
) -> dict[str, Any] | None:
    from datetime import datetime as dt

    patch = {
        "sheets_rows": sheet_rows,
        "sheets_synced_at": dt.now(KYIV).isoformat(timespec="seconds"),
    }
    saved = storage.merge_order_payload(int(order["id"]), patch)
    storage.update_order_flags(int(order["id"]), sheets_sync_status=sync_status)
    return storage.get_order(int(order["id"])) or saved


def append_order_rows(
    ws: gspread.Worksheet,
    rows: list[list[Any]],
) -> list[int]:
    if not rows:
        return []
    result = ws.append_rows(
        rows,
        value_input_option="USER_ENTERED",
        insert_data_option="INSERT_ROWS",
        table_range="A1",
    )
    # gspread returns dict-like with updatedRange
    updated = ""
    if isinstance(result, dict):
        updated = str(
            (result.get("updates") or {}).get("updatedRange")
            or result.get("updatedRange")
            or ""
        )
    start = _parse_updated_range_start_row(updated)
    if start is None:
        # fallback: last rows
        all_vals = ws.col_values(COL_ORDER_NO)
        start = max(2, len(all_vals) - len(rows) + 1)
    return list(range(start, start + len(rows)))


def update_rows_values(
    ws: gspread.Worksheet,
    row_numbers: list[int],
    rows: list[list[Any]],
) -> None:
    if not row_numbers or not rows:
        return
    data = []
    for row_num, values in zip(row_numbers, rows):
        data.append(
            {
                "range": f"A{row_num}:R{row_num}",
                "values": [values],
            }
        )
    # leftover old rows (cart shrunk): clear product fields / mark
    if len(row_numbers) > len(rows):
        for row_num in row_numbers[len(rows) :]:
            data.append(
                {
                    "range": f"E{row_num}:J{row_num}",
                    "values": [["", "", "", "", "", ""]],
                }
            )
            data.append(
                {
                    "range": f"O{row_num}",
                    "values": [["видалено з замовлення"]],
                }
            )
    ws.batch_update(data, value_input_option="USER_ENTERED")


def update_lifecycle_columns(
    ws: gspread.Worksheet,
    row_numbers: list[int],
    *,
    ttn: str,
    status: str,
    note: str,
    settlement: str,
) -> None:
    if not row_numbers:
        return
    data = []
    for row_num in row_numbers:
        data.extend(
            [
                {"range": f"M{row_num}", "values": [[ttn]]},
                {"range": f"N{row_num}", "values": [[status]]},
                {"range": f"O{row_num}", "values": [[note]]},
                {"range": f"Q{row_num}", "values": [[settlement]]},
            ]
        )
    ws.batch_update(data, value_input_option="USER_ENTERED")


def sync_order_to_sheet(
    storage: AppStorage,
    order: dict[str, Any] | None,
    *,
    catalog: Any = None,
    full: bool = False,
) -> dict[str, Any] | None:
    """
    Записати / оновити замовлення в Sheet.
    full=True — перезаписати всі 18 колонок (create / edit cart).
    full=False — якщо рядки вже є, оновити ТТН/статус/примітку/розрахунок.
    """
    if not order or not order.get("id"):
        return order
    sync_flag = str(order.get("sheets_sync_status") or "pending").strip()
    if sync_flag == "hold_pdf":
        logger.info(
            "orders sheet skip hold_pdf order=%s", order.get("order_number")
        )
        return order

    payload = order.get("payload") or {}
    existing_meta = payload.get("sheets_rows") if isinstance(payload.get("sheets_rows"), list) else []
    row_numbers = [
        int(x.get("row"))
        for x in existing_meta
        if isinstance(x, dict) and str(x.get("row") or "").isdigit()
    ]

    try:
        ws = _open_orders_worksheet(storage)
        built = build_sheet_rows(storage, order, catalog=catalog)
        if not built:
            storage.update_order_flags(int(order["id"]), sheets_sync_status="synced")
            return order

        if not row_numbers:
            # спроба знайти за № заказа (ретрай після збою meta)
            row_numbers = find_sheet_rows_by_order_number(
                ws, str(order.get("order_number") or "")
            )

        if not row_numbers:
            row_numbers = append_order_rows(ws, built)
            meta = []
            cart = (order.get("payload") or {}).get("cart") or []
            for i, row_num in enumerate(row_numbers):
                item = cart[i] if i < len(cart) and isinstance(cart[i], dict) else {}
                code = str(item.get("code") or "")
                color = str(item.get("color") or "")
                if not code and i < len(built):
                    code = str(built[i][5] or "")
                if not color and i < len(built):
                    color = str(built[i][6] or "")
                meta.append({"row": row_num, "code": code, "color": color})
            order = _save_sheet_meta(
                storage, order, sheet_rows=meta, sync_status="synced"
            )
            logger.info(
                "orders sheet append order=%s rows=%s",
                order.get("order_number") if order else "",
                row_numbers,
            )
            return order

        if full or len(row_numbers) != len(built):
            # дописуємо зайві рядки кошика; зайві старі — чистимо в update_rows_values
            if len(built) > len(row_numbers):
                extra = append_order_rows(ws, built[len(row_numbers) :])
                row_numbers = [*row_numbers, *extra]
            update_rows_values(ws, row_numbers, built)
        else:
            update_lifecycle_columns(
                ws,
                row_numbers,
                ttn=str(built[0][12] if built else ""),
                status=str(built[0][13] if built else ""),
                note=str(built[0][14] if built else ""),
                settlement=str(built[0][16] if built else ""),
            )

        cart = (order.get("payload") or {}).get("cart") or []
        meta = []
        usable = row_numbers[: max(len(built), 1)]
        for i, row_num in enumerate(usable):
            item = cart[i] if i < len(cart) and isinstance(cart[i], dict) else {}
            code = str(item.get("code") or "")
            color = str(item.get("color") or "")
            if not code and i < len(built):
                code = str(built[i][5] or "")
            if not color and i < len(built):
                color = str(built[i][6] or "")
            meta.append({"row": row_num, "code": code, "color": color})
        order = _save_sheet_meta(
            storage, order, sheet_rows=meta, sync_status="synced"
        )
        logger.info(
            "orders sheet update order=%s rows=%s full=%s",
            order.get("order_number") if order else "",
            row_numbers,
            full,
        )
        return order
    except Exception:
        logger.exception(
            "orders sheet sync failed order=%s", order.get("order_number")
        )
        try:
            storage.update_order_flags(int(order["id"]), sheets_sync_status="pending")
        except Exception:
            pass
        return storage.get_order(int(order["id"])) or order


def sync_order_by_id(
    storage: AppStorage,
    order_id: int,
    *,
    catalog: Any = None,
    full: bool = False,
) -> dict[str, Any] | None:
    order = storage.get_order(int(order_id))
    if not order:
        return None
    return sync_order_to_sheet(storage, order, catalog=catalog, full=full)


def run_pending_orders_sheet_sync(
    storage: AppStorage,
    *,
    catalog: Any = None,
    limit: int = 40,
) -> dict[str, int]:
    """Ретрай для sheets_sync_status=pending (не hold_pdf)."""
    orders = storage.list_orders_by_sheets_sync_status("pending", limit=limit)
    stats = {"checked": len(orders), "synced": 0, "errors": 0, "skipped": 0}
    for order in orders:
        if str(order.get("sheets_sync_status") or "") == "hold_pdf":
            stats["skipped"] += 1
            continue
        before = str(order.get("sheets_sync_status") or "")
        saved = sync_order_to_sheet(storage, order, catalog=catalog, full=True)
        after = str((saved or order).get("sheets_sync_status") or "")
        if after == "synced":
            stats["synced"] += 1
        elif after == before:
            stats["errors"] += 1
    return stats
