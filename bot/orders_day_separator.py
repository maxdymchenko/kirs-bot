"""Синій рядок-роздільник днів відправки в листі «Заказы».

Пн–пт і нд о 14:01, сб о 13:01 Київ — дописати в кінець ряд з датою
наступного дня. Без зсуву і без запису поверх замовлень.

Неділя теж потрібна: інакше дата понеділка ніколи не з’являється
(сб пише неділю, пн 14:01 вже пише вівторок).
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
WEEKDAY_SLOT = time(14, 1)
SATURDAY_SLOT = time(13, 1)
SETTINGS_KEY = "orders_day_separator_state"
LOOKBACK_DAYS = 8


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def separator_slot_for(weekday: int) -> time | None:
    """Пн–пт/нд 14:01, сб 13:01."""
    if weekday == 5:
        return SATURDAY_SLOT
    if 0 <= weekday <= 6:
        return WEEKDAY_SLOT
    return None


def next_ship_date_label(now: datetime | None = None) -> str:
    dt = now_kyiv(now)
    nxt = dt.date() + timedelta(days=1)
    return nxt.strftime("%d.%m.%Y")


def due_separator_labels(now: datetime | None = None) -> list[str]:
    """Дати, які вже мали з’явитися після минулих слотів (без майбутніх)."""
    dt = now_kyiv(now)
    labels: list[str] = []
    seen: set[str] = set()
    for offset in range(LOOKBACK_DAYS, -1, -1):
        day = dt.date() - timedelta(days=offset)
        slot = separator_slot_for(day.weekday())
        if slot is None:
            continue
        target = datetime.combine(day, slot, tzinfo=KYIV)
        if dt < target:
            continue
        label = (day + timedelta(days=1)).strftime("%d.%m.%Y")
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def seconds_until_next_separator_slot(
    *,
    now: datetime | None = None,
    allow_current_slot: bool = False,
) -> float:
    dt = now_kyiv(now)
    slot = separator_slot_for(dt.weekday())
    if (
        allow_current_slot
        and slot is not None
        and (dt.hour, dt.minute) >= (slot.hour, slot.minute)
    ):
        return 0.0
    candidates: list[datetime] = []
    for day_offset in range(0, 8):
        day = dt.date() + timedelta(days=day_offset)
        day_slot = separator_slot_for(day.weekday())
        if day_slot is None:
            continue
        target = datetime.combine(day, day_slot, tzinfo=KYIV)
        if target > dt:
            candidates.append(target)
    if not candidates:
        return 3600.0
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
    due = due_separator_labels(dt)
    if force:
        label = next_ship_date_label(dt)
        if label not in due:
            due = [*due, label]
    if not due:
        return {"ok": True, "skipped": "before_slot", "day": day}

    from bot.orders_sheets import (
        _open_orders_worksheet,
        _parse_sheet_date,
        append_day_separator_row,
        day_separator_exists,
        latest_day_separator_date,
    )

    ws = _open_orders_worksheet(storage)
    last_sep = latest_day_separator_date(ws)
    last_d = _parse_sheet_date(last_sep)
    pending: list[str] = []
    for date_s in due:
        parsed = _parse_sheet_date(date_s)
        if last_d and parsed and parsed <= last_d:
            continue
        pending.append(date_s)
    if not pending:
        _save_state(
            storage,
            {
                "last_run_date": day,
                "last_at": dt.isoformat(timespec="seconds"),
                "due": due,
                "added": [],
                "already": due,
                "last_separator": last_sep,
            },
        )
        return {
            "ok": True,
            "skipped": "up_to_date",
            "day": day,
            "due": due,
            "last_separator": last_sep,
        }

    added: list[dict[str, Any]] = []
    already: list[str] = []
    for date_s in pending:
        if day_separator_exists(ws, date_s):
            already.append(date_s)
            continue
        row = append_day_separator_row(ws, date_s)
        added.append({"date": date_s, "row": row})

    _save_state(
        storage,
        {
            "last_run_date": day,
            "last_at": dt.isoformat(timespec="seconds"),
            "due": due,
            "added": added,
            "already": already,
        },
    )
    return {
        "ok": True,
        "day": day,
        "due": due,
        "added": added,
        "already": already,
    }
