"""Дайджест у групу упаковки: 12:00 і 14:00 (Київ).

12:00 — усі замовлення в черзі «На пакування» (розбивка за розташуванням — пізніше).
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


def _slot_key(day: datetime, hour: int) -> str:
    return f"{day.date().isoformat()}T{hour:02d}"


def _day_key(day: datetime) -> str:
    return day.date().isoformat()


def packing_orders(storage: AppStorage, *, limit: int = 500) -> list[dict[str, Any]]:
    """Поточна черга «На пакування» (та сама логіка, що в кабінеті комірника)."""
    return list_warehouse_queue(storage, stage="packing", limit=limit)


def format_noon_digest(orders: list[dict[str, Any]]) -> str:
    count = len(orders)
    return (
        f"📦 На пакування (12:00)\n\n"
        f"Замовлень: {count} {_orders_word(count)}.\n\n"
        "Розбивка за розташуванням на складі — незабаром."
    )


def format_afternoon_digest(orders: list[dict[str, Any]]) -> str:
    count = len(orders)
    return (
        f"📦 Доповнення до пакування (14:00)\n\n"
        f"Нових замовлень після 12:00: {count} {_orders_word(count)}.\n"
        "Ці позиції не входили до списку о 12:00."
    )


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {"sent": [], "noon_ids_by_day": {}}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {"sent": [], "noon_ids_by_day": {}}
    if not isinstance(data, dict):
        return {"sent": [], "noon_ids_by_day": {}}
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
    return {
        "sent": [str(x) for x in sent][-60:],
        "noon_ids_by_day": cleaned,
    }


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    noon_map = state.get("noon_ids_by_day") or {}
    # тримаємо лише останні ~14 днів
    if isinstance(noon_map, dict) and len(noon_map) > 14:
        keys = sorted(noon_map.keys())[-14:]
        noon_map = {k: noon_map[k] for k in keys}

    payload = json.dumps(
        {
            "sent": list(state.get("sent") or [])[-60:],
            "noon_ids_by_day": noon_map,
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

    orders = packing_orders(storage)
    day = _day_key(now)

    if slot_hour == HOUR_NOON:
        selected = orders
        text = format_noon_digest(selected) if selected else ""
        # навіть якщо 0 — зберігаємо порожній список, щоб 14:00 знала базу
        state.setdefault("noon_ids_by_day", {})[day] = [
            int(o["id"]) for o in selected if o.get("id") is not None
        ]
    else:
        noon_ids = {
            int(x)
            for x in (state.get("noon_ids_by_day") or {}).get(day, [])
        }
        selected = [
            o
            for o in orders
            if o.get("id") is not None and int(o["id"]) not in noon_ids
        ]
        text = format_afternoon_digest(selected) if selected else ""

    stats["count"] = len(selected)

    if not selected:
        # немає замовлень — без повідомлення, слот позначаємо виконаним
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["skipped"] = 1
        stats["reason"] = "empty"
        return stats

    try:
        result = notify(target, text)
        if hasattr(result, "__await__"):
            await result
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["sent"] = 1
    except Exception:
        stats["errors"] = 1
        logger.exception(
            "packing digest notify failed hour=%s chat=%s", slot_hour, target
        )
    return stats
