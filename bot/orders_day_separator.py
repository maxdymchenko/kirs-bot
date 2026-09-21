"""Синій рядок-роздільник днів відправки в листі «Заказы».

Пн–пт о 14:01 Київ — дописати в кінець ряд з датою наступного дня.
Без зсуву і без запису поверх інших замовлень.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
SLOT_HOUR = 14
SLOT_MINUTE = 1
SETTINGS_KEY = "orders_day_separator_state"


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def next_ship_date_label(now: datetime | None = None) -> str:
    dt = now_kyiv(now)
    nxt = dt.date() + timedelta(days=1)
    return nxt.strftime("%d.%m.%Y")


def seconds_until_next_separator_slot(
    *,
    now: datetime | None = None,
    allow_current_slot: bool = False,
) -> float:
    dt = now_kyiv(now)
    if (
        allow_current_slot
        and dt.weekday() < 5
        and (dt.hour, dt.minute) >= (SLOT_HOUR, SLOT_MINUTE)
    ):
        return 0.0
    candidates: list[datetime] = []
    for day_offset in range(0, 8):
        day = dt.date() + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        target = datetime.combine(day, time(SLOT_HOUR, SLOT_MINUTE), tzinfo=KYIV)
        if target > dt:
            candidates.append(target)
    return max(30.0, (candidates[0] - dt).total_seconds())


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    body = json.dumps(state, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SETTINGS_KEY, body, _now()),
        )
        conn.commit()


def run_day_separator_pass(
    storage: AppStorage,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    dt = now_kyiv(now)
    day = dt.date().isoformat()
    date_s = next_ship_date_label(dt)
    state = _load_state(storage)
    if not force:
        if dt.weekday() >= 5:
            return {"ok": True, "skipped": "weekend", "day": day}
        if (dt.hour, dt.minute) < (SLOT_HOUR, SLOT_MINUTE):
            return {"ok": True, "skipped": "before_slot", "day": day}
        if str(state.get("last_run_date") or "") == day:
            return {"ok": True, "skipped": True, "day": day, "date": date_s}

    from bot.orders_sheets import (
        _open_orders_worksheet,
        append_day_separator_row,
        day_separator_exists,
    )

    ws = _open_orders_worksheet(storage)
    if day_separator_exists(ws, date_s):
        _save_state(
            storage,
            {
                "last_run_date": day,
                "last_at": dt.isoformat(timespec="seconds"),
                "date": date_s,
                "already": True,
                "row": 0,
            },
        )
        return {"ok": True, "already": True, "day": day, "date": date_s, "row": 0}

    row = append_day_separator_row(ws, date_s)
    _save_state(
        storage,
        {
            "last_run_date": day,
            "last_at": dt.isoformat(timespec="seconds"),
            "date": date_s,
            "already": False,
            "row": row,
        },
    )
    return {"ok": True, "day": day, "date": date_s, "row": row}
