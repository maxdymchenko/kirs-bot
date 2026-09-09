"""Дайджест у групу упаковки: 12:00 і 14:00 (Київ).

12:00 — черга «На пакування»: замовлення дропперов + Prom/Rozetka/ручні з листа «Заказы».
14:00 — лише ті, що зʼявились після полудня (не були в списку 12:00).
Якщо замовлень немає — повідомлення не надсилаємо.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.warehouse import list_warehouse_queue

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
DIGEST_HOURS = (12, 14)
HOUR_NOON = 12
HOUR_AFTERNOON = 14
SETTINGS_KEY = "packing_digest_state"
DEFAULT_CHAT_ID = "-1003912251878"

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

NotifyFn = Callable[[str, str], Awaitable[None] | None]


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def _orders_word(n: int) -> str:
    abs_n = abs(int(n))
    mod10 = abs_n % 10
    mod100 = abs_n % 100
    if mod10 == 1 and mod100 != 11:
        return "замовлення"
    if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        return "замовлення"
    return "замовлень"


def _clean_location(raw: Any) -> str:
    """Колонка J / розташування: пусто і заглушки типу «Уточнення» відсікаємо."""
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


def _extract_packing_items(
    orders: list[dict[str, Any]],
    catalog: Any = None,
) -> tuple[list[dict[str, Any]], int]:
    """Витягує всі товарні позиції для пакування з розкладкою по локаціях."""
    all_items: list[dict[str, Any]] = []
    total_qty = 0

    for order in orders:
        order_num = str(order.get("order_number") or order.get("id") or "—").strip()
        payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
        cart = payload.get("cart") if isinstance(payload.get("cart"), list) else []

        if not cart:
            all_items.append(
                {
                    "order_number": order_num,
                    "name": "",
                    "code": "",
                    "color": "",
                    "qty": 1,
                    "location": "",
                    "source": "",
                }
            )
            total_qty += 1
            continue

        for item in cart:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or "").strip()
            color = str(item.get("color") or "").strip()
            qty = max(1, int(item.get("qty") or 1))
            loc = _clean_location(item.get("location"))

            if not loc and catalog is not None and code:
                try:
                    from bot.orders_sheets import _lookup_variant_meta

                    _, loc_cat, *_rest = _lookup_variant_meta(catalog, code, color)
                    loc = _clean_location(loc_cat)
                except Exception:
                    pass

            source = str(
                item.get("source") or payload.get("market_source") or ""
            ).strip()
            all_items.append(
                {
                    "order_number": order_num,
                    "name": name,
                    "code": code,
                    "color": color,
                    "qty": qty,
                    "location": loc,
                    "source": source,
                }
            )
            total_qty += qty

    return all_items, total_qty


def _slot_key(day: datetime, hour: int) -> str:
    return f"{day.date().isoformat()}T{hour:02d}"


def _day_key(day: datetime) -> str:
    return day.date().isoformat()


def packing_orders(storage: AppStorage, *, limit: int = 500) -> list[dict[str, Any]]:
    """Поточна черга «На пакування» (та сама логіка, що в кабінеті комірника)."""
    return list_warehouse_queue(storage, stage="packing", limit=limit)


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


def list_sheet_packing_orders(storage: AppStorage) -> list[dict[str, Any]]:
    """Рядки Prom / Rozetka / ручні з листа «Заказы», які ще на складі."""
    try:
        from bot.orders_sheets import _open_orders_worksheet

        ws = _open_orders_worksheet(storage)
        rows = ws.get_all_values()
    except Exception:
        logger.exception("packing digest: failed to read marketplace rows from sheet")
        return []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[1:], start=2):
        while len(row) < 18:
            row.append("")
        order_no = str(row[1] or "").strip()
        source = str(row[10] or "").strip()
        if not order_no or not _is_market_or_manual_source(source, order_no):
            continue
        if not _is_sheet_row_still_packing(row[13]):
            continue
        code = str(row[5] or "").strip()
        color = str(row[6] or "").strip()
        name = str(row[4] or "").strip()
        qty = _sheet_qty(row[7])
        loc = _clean_location(row[17] if len(row) > 17 else "")
        sheet_key = f"{order_no}|{code}|{color}|{idx}"
        out.append(
            {
                "id": None,
                "order_number": order_no,
                "payload": {
                    "cart": [
                        {
                            "name": name,
                            "code": code,
                            "color": color,
                            "qty": qty,
                            "location": loc,
                            "source": source,
                        }
                    ],
                    "sheet_key": sheet_key,
                    "market_source": source,
                },
            }
        )
    return out


def _sheet_key_of(order: dict[str, Any]) -> str:
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    return str(payload.get("sheet_key") or "").strip()


def merge_packing_orders(
    dropper_orders: list[dict[str, Any]],
    sheet_orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen_nos = {
        str(order.get("order_number") or "").strip()
        for order in dropper_orders
        if str(order.get("order_number") or "").strip()
    }
    extra = [
        order
        for order in sheet_orders
        if str(order.get("order_number") or "").strip() not in seen_nos
    ]
    return [*dropper_orders, *extra]


def format_packing_digest_messages(
    orders: list[dict[str, Any]],
    locations_order: list[str] | None = None,
    *,
    catalog: Any = None,
    is_noon: bool = True,
    max_len: int = 3800,
) -> list[str]:
    """Формує структуровані повідомлення дайджесту пакування за градацією локацій."""
    count = len(orders)
    if not count:
        return []

    items, total_qty = _extract_packing_items(orders, catalog)
    loc_order = [str(x).strip() for x in (locations_order or []) if str(x).strip()]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        loc = item["location"]
        grouped.setdefault(loc, []).append(item)

    order_map = {name.casefold(): idx for idx, name in enumerate(loc_order)}

    def _sort_key(loc_name: str) -> tuple[int, int, str]:
        if not loc_name:
            return (2, 0, "")
        folded = loc_name.casefold()
        if folded in order_map:
            return (0, order_map[folded], loc_name)
        return (1, 0, folded)

    sorted_locs = sorted(grouped.keys(), key=_sort_key)

    title = "📦 На пакування (12:00)" if is_noon else "📦 Доповнення до пакування (14:00)"
    subtitle = (
        f"Замовлень: {count} {_orders_word(count)} · Всього: {total_qty} шт."
        if is_noon
        else f"Нових замовлень після 12:00: {count} {_orders_word(count)} · Всього: {total_qty} шт."
    )

    blocks: list[str] = [f"{title}\n{subtitle}"]

    for loc in sorted_locs:
        loc_items = grouped[loc]
        loc_qty = sum(it["qty"] for it in loc_items)
        loc_header = (
            f"📍 {loc} ({loc_qty} шт):"
            if loc
            else f"📍 Без локації / Уточнення ({loc_qty} шт):"
        )

        lines = [loc_header]
        for it in loc_items:
            code = it["code"]
            color = it["color"]
            name = it["name"]
            qty = it["qty"]
            ord_num = it["order_number"]

            details = []
            if code:
                details.append(f"Код: {code}")
            if color:
                details.append(color)
            elif name and not code:
                details.append(name[:40])

            desc = " · ".join(details) if details else (name[:40] or "Товар")
            tail = f"№ {ord_num}"
            if it.get("source"):
                tail += f" · {it['source']}"
            lines.append(f"• {desc} — {qty} шт ({tail})")

        blocks.append("\n".join(lines))

    messages: list[str] = []
    current_chunk = blocks[0]

    for block in blocks[1:]:
        if len(current_chunk) + len(block) + 2 > max_len:
            messages.append(current_chunk.strip())
            current_chunk = block
        else:
            current_chunk += "\n\n" + block

    if current_chunk.strip():
        messages.append(current_chunk.strip())

    return messages


def format_noon_digest(
    orders: list[dict[str, Any]],
    locations_order: list[str] | None = None,
    catalog: Any = None,
) -> str:
    msgs = format_packing_digest_messages(
        orders, locations_order, catalog=catalog, is_noon=True
    )
    return "\n\n".join(msgs)


def format_afternoon_digest(
    orders: list[dict[str, Any]],
    locations_order: list[str] | None = None,
    catalog: Any = None,
) -> str:
    msgs = format_packing_digest_messages(
        orders, locations_order, catalog=catalog, is_noon=False
    )
    return "\n\n".join(msgs)


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {"sent": [], "noon_ids_by_day": {}, "noon_sheet_keys_by_day": {}}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {"sent": [], "noon_ids_by_day": {}, "noon_sheet_keys_by_day": {}}
    if not isinstance(data, dict):
        return {"sent": [], "noon_ids_by_day": {}, "noon_sheet_keys_by_day": {}}
    sent = data.get("sent")
    if not isinstance(sent, list):
        sent = []
    noon_map = data.get("noon_ids_by_day")
    if not isinstance(noon_map, dict):
        noon_map = {}
    cleaned: dict[str, list[int]] = {}
    for day, ids in noon_map.items():
        if not isinstance(ids, list):
            continue
        cleaned[str(day)] = [int(x) for x in ids if str(x).strip().lstrip("-").isdigit()]
    sheet_map = data.get("noon_sheet_keys_by_day")
    if not isinstance(sheet_map, dict):
        sheet_map = {}
    sheet_cleaned: dict[str, list[str]] = {}
    for day, keys in sheet_map.items():
        if not isinstance(keys, list):
            continue
        sheet_cleaned[str(day)] = [str(x) for x in keys if str(x).strip()]
    return {
        "sent": [str(x) for x in sent][-60:],
        "noon_ids_by_day": cleaned,
        "noon_sheet_keys_by_day": sheet_cleaned,
    }


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    noon_map = state.get("noon_ids_by_day") or {}
    sheet_map = state.get("noon_sheet_keys_by_day") or {}
    # тримаємо лише останні ~14 днів
    if isinstance(noon_map, dict) and len(noon_map) > 14:
        keys = sorted(noon_map.keys())[-14:]
        noon_map = {k: noon_map[k] for k in keys}
    if isinstance(sheet_map, dict) and len(sheet_map) > 14:
        keys = sorted(sheet_map.keys())[-14:]
        sheet_map = {k: sheet_map[k] for k in keys}

    payload = json.dumps(
        {
            "sent": list(state.get("sent") or [])[-60:],
            "noon_ids_by_day": noon_map,
            "noon_sheet_keys_by_day": sheet_map,
        },
        ensure_ascii=False,
    )
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SETTINGS_KEY, payload, _now()),
        )
        conn.commit()


def seconds_until_next_digest_slot(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> tuple[float, int]:
    """Секунди до наступного слоту 12:00 або 14:00 (Київ)."""
    now = now_kyiv(now)
    if allow_current_hour and now.hour in DIGEST_HOURS:
        return 0.0, now.hour

    candidates: list[tuple[datetime, int]] = []
    for day_offset in (0, 1, 2):
        day = now.date() + timedelta(days=day_offset)
        for hour in DIGEST_HOURS:
            target = datetime.combine(day, time(hour, 0), tzinfo=KYIV)
            if target > now:
                candidates.append((target, hour))
    candidates.sort(key=lambda x: x[0])
    target, hour = candidates[0]
    return max(30.0, (target - now).total_seconds()), hour


async def run_packing_digest_pass(
    storage: AppStorage,
    notify: NotifyFn,
    *,
    chat_id: str,
    now: datetime | None = None,
    hour: int | None = None,
    force: bool = False,
    catalog: Any = None,
) -> dict[str, Any]:
    now = now_kyiv(now)
    slot_hour = int(hour if hour is not None else now.hour)
    target = str(chat_id or "").strip()
    stats: dict[str, Any] = {
        "hour": slot_hour,
        "count": 0,
        "sent": 0,
        "skipped": 0,
        "errors": 0,
        "chat_id": target,
    }
    if not target:
        stats["skipped"] = 1
        stats["reason"] = "no_chat"
        return stats
    if slot_hour not in DIGEST_HOURS and not force:
        stats["skipped"] = 1
        return stats

    key = _slot_key(now, slot_hour)
    state = _load_state(storage)
    if key in state["sent"] and not force:
        stats["skipped"] = 1
        return stats

    dropper_orders = packing_orders(storage)
    sheet_orders = list_sheet_packing_orders(storage)
    orders = merge_packing_orders(dropper_orders, sheet_orders)
    day = _day_key(now)
    locations_order = storage.get_warehouse_locations_order()

    if slot_hour == HOUR_NOON:
        selected = orders
        messages = (
            format_packing_digest_messages(
                selected, locations_order, catalog=catalog, is_noon=True
            )
            if selected
            else []
        )
        # навіть якщо 0 — зберігаємо порожній список, щоб 14:00 знала базу
        state.setdefault("noon_ids_by_day", {})[day] = [
            int(o["id"]) for o in selected if o.get("id") is not None
        ]
        state.setdefault("noon_sheet_keys_by_day", {})[day] = [
            key for o in selected if (key := _sheet_key_of(o))
        ]
    else:
        noon_ids = {
            int(x)
            for x in (state.get("noon_ids_by_day") or {}).get(day, [])
        }
        noon_sheet = {
            str(x)
            for x in (state.get("noon_sheet_keys_by_day") or {}).get(day, [])
        }
        selected = []
        for o in orders:
            sheet_key = _sheet_key_of(o)
            if sheet_key:
                if sheet_key not in noon_sheet:
                    selected.append(o)
            elif o.get("id") is not None and int(o["id"]) not in noon_ids:
                selected.append(o)
        messages = (
            format_packing_digest_messages(
                selected, locations_order, catalog=catalog, is_noon=False
            )
            if selected
            else []
        )

    stats["count"] = len(selected)

    if not selected or not messages:
        # немає замовлень — без повідомлення, слот позначаємо виконаним
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["skipped"] = 1
        stats["reason"] = "empty"
        return stats

    try:
        for msg in messages:
            result = notify(target, msg)
            if hasattr(result, "__await__"):
                await result
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["sent"] = len(messages)
    except Exception:
        stats["errors"] = 1
        logger.exception(
            "packing digest notify failed hour=%s chat=%s", slot_hour, target
        )
    return stats

