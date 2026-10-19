"""Вікно редагування замовлень дроппером (Київський час).

Після відсічки пакування дроппер не може сам редагувати/скасовувати:
пн–пт і нд з 14:00, сб з 13:00. До півночі — лише запит власнику.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
DROPPER_EDIT_LOCK_ENABLED = True
WEEKDAY_LOCK = time(14, 0)
SATURDAY_LOCK = time(13, 0)


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def dropper_edit_lock_start(weekday: int) -> time:
    """Пн–пт/нд 14:00, сб 13:00."""
    if weekday == 5:
        return SATURDAY_LOCK
    return WEEKDAY_LOCK


def lock_start_label(weekday: int) -> str:
    start = dropper_edit_lock_start(weekday)
    return start.strftime("%H:%M")


def is_dropper_edit_locked(now: datetime | None = None) -> bool:
    """True після відсічки пакування і до кінця доби (Europe/Kyiv)."""
    if not DROPPER_EDIT_LOCK_ENABLED:
        return False
    dt = now_kyiv(now)
    start = dropper_edit_lock_start(dt.weekday())
    return dt.timetz().replace(tzinfo=None) >= start


def _next_lock_at(dt: datetime) -> datetime:
    start = dropper_edit_lock_start(dt.weekday())
    today_lock = datetime.combine(dt.date(), start, tzinfo=KYIV)
    if dt < today_lock:
        return today_lock
    nxt = dt.date() + timedelta(days=1)
    return datetime.combine(nxt, dropper_edit_lock_start(nxt.weekday()), tzinfo=KYIV)


def _next_open_at(dt: datetime) -> datetime:
    nxt = dt.date() + timedelta(days=1)
    return datetime.combine(nxt, time(0, 0), tzinfo=KYIV)


def dropper_edit_window_info(now: datetime | None = None) -> dict[str, Any]:
    dt = now_kyiv(now)
    locked = is_dropper_edit_locked(dt)
    label = lock_start_label(dt.weekday())
    if not DROPPER_EDIT_LOCK_ENABLED:
        message = "Редагування відкрите, поки замовлення не відправлено."
        next_open = None
        next_lock = None
    elif locked:
        message = (
            f"Після {label} (Київ) редагування та скасування закриті — "
            "замовлення вже в черзі на пакування. "
            "Можна подати запит на виправлення власнику. "
            "Знову відкриється після опівночі."
        )
        next_open = _next_open_at(dt)
        next_lock = None
    else:
        message = (
            f"Редагування відкрите до {label} (Київ). "
            "Після цього правки і скасування закриті до опівночі."
        )
        next_lock = _next_lock_at(dt)
        next_open = None

    return {
        "timezone": "Europe/Kyiv",
        "locked": locked,
        "editable": not locked,
        "lock_start": label,
        "lock_end": "00:00",
        "now": dt.isoformat(timespec="seconds"),
        "next_open_at": next_open.isoformat(timespec="seconds") if next_open else "",
        "next_lock_at": next_lock.isoformat(timespec="seconds") if next_lock else "",
        "message": message,
    }
