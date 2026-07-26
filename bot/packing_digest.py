"""Дайджест власнику: скільки замовлень чекають на упаковку/відправку (10:00 і 22:00 Київ)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.np_fulfillment import AWAITING_SHIPMENT_STATUSES

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
DIGEST_HOURS = (10, 22)
SETTINGS_KEY = "packing_digest_state"

OwnerNotifyFn = Callable[[str], Awaitable[None] | None]


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def count_orders_awaiting_pack(storage: AppStorage) -> int:
    """
    Замовлення на складі власника, що ще чекають упаковки/відправки:
    не скасовані, не власна ТТН дроппера, статус ТТН ще «очікує відправлення»,
    без hold через розбіжність PDF/ТТН.
    """
    statuses = tuple(sorted(AWAITING_SHIPMENT_STATUSES))
    placeholders = ",".join("?" for _ in statuses)
    with storage._connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM orders
            WHERE status != 'cancelled'
              AND own_ttn = 0
              AND COALESCE(NULLIF(ttn_status, ''), 'none') IN ({placeholders})
              AND COALESCE(sheets_sync_status, '') != 'hold_pdf'
              AND IFNULL(payload_json, '') NOT LIKE '%"ttn_pdf_hold": true%'
              AND IFNULL(payload_json, '') NOT LIKE '%"ttn_pdf_hold":true%'
            """,
            statuses,
        ).fetchone()
    return int(row["c"] or 0) if row else 0


def format_packing_digest_plain(*, count: int, hour: int) -> str:
    """Текст для Telegram (без HTML)."""
    if hour == 22:
        when = "на завтра"
        title = "📦 Обсяг на завтра (упаковка / відправка)"
    else:
        when = "на сьогодні"
        title = "📦 Обсяг на сьогодні (упаковка / відправка)"
    word = _orders_word(count)
    return (
        f"{title}\n\n"
        f"Замовлень {when}: {count} {word}.\n"
        "Це замовлення, що очікують упаковки та відправки зі складу."
    )


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


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {"sent": []}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {"sent": []}
    if not isinstance(data, dict):
        return {"sent": []}
    sent = data.get("sent")
    if not isinstance(sent, list):
        sent = []
    return {"sent": [str(x) for x in sent][-60:]}


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    payload = json.dumps(
        {"sent": list(state.get("sent") or [])[-60:]},
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
    """
    Секунди до наступного слоту 10:00 або 22:00 (Київ).
    Повертає (delay_sec, hour).
    """
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
    owner_notify: OwnerNotifyFn,
    *,
    now: datetime | None = None,
    hour: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    now = now_kyiv(now)
    slot_hour = int(hour if hour is not None else now.hour)
    stats: dict[str, Any] = {
        "hour": slot_hour,
        "count": 0,
        "sent": 0,
        "skipped": 0,
        "errors": 0,
    }
    if slot_hour not in DIGEST_HOURS and not force:
        stats["skipped"] = 1
        return stats

    key = _slot_key(now, slot_hour)
    state = _load_state(storage)
    if key in state["sent"] and not force:
        stats["skipped"] = 1
        return stats

    count = count_orders_awaiting_pack(storage)
    stats["count"] = count
    text = format_packing_digest_plain(count=count, hour=slot_hour)
    try:
        result = owner_notify(text)
        if hasattr(result, "__await__"):
            await result
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["sent"] = 1
    except Exception:
        stats["errors"] = 1
        logger.exception("packing digest notify failed hour=%s", slot_hour)
    return stats
