"""Вікно редагування замовлень дроппером (Київський час).

Інтервал 11:50–14:30 (розноска кладовщику) тимчасово вимкнено —
дроппер може редагувати/скасовувати в будь-який час, поки замовлення
ще не відправлено. Щоб повернути блок, поставте DROPPER_EDIT_LOCK_ENABLED = True.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
# Тимчасово вимкнено на прохання власника (2026-09-12).
DROPPER_EDIT_LOCK_ENABLED = False
LOCK_START = time(11, 50)
LOCK_END = time(14, 30)
LOCK_START_LABEL = "11:50"
LOCK_END_LABEL = "14:30"


def now_kyiv() -> datetime:
    return datetime.now(KYIV)


def is_dropper_edit_locked(now: datetime | None = None) -> bool:
    """True у «закриту годину» 11:50 ≤ t < 14:30 (Europe/Kyiv), якщо вікно увімкнено."""
    if not DROPPER_EDIT_LOCK_ENABLED:
        return False
    dt = now or now_kyiv()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    t = dt.timetz().replace(tzinfo=None)
    return LOCK_START <= t < LOCK_END


def dropper_edit_window_info(now: datetime | None = None) -> dict[str, Any]:
    dt = now or now_kyiv()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    locked = is_dropper_edit_locked(dt)
    today = dt.date()
    start_dt = datetime.combine(today, LOCK_START, tzinfo=KYIV)
    end_dt = datetime.combine(today, LOCK_END, tzinfo=KYIV)
    if not DROPPER_EDIT_LOCK_ENABLED:
        message = "Редагування відкрите, поки замовлення не відправлено."
        next_open = None
        next_lock = None
    elif locked:
        message = (
            f"Зараз {LOCK_START_LABEL}–{LOCK_END_LABEL} (Київ) — редагування та "
            "скасування тимчасово закриті (розноска замовлень). "
            "Можна подати запит на виправлення власнику."
        )
        next_open = end_dt
    else:
        message = (
            f"Редагування відкрите. З {LOCK_START_LABEL} до {LOCK_END_LABEL} "
            "(Київ) можливість буде закрита."
        )
        # наступне закриття
        if dt.timetz().replace(tzinfo=None) < LOCK_START:
            next_lock = start_dt
        else:
            next_lock = start_dt + timedelta(days=1)
        next_open = None

    return {
        "timezone": "Europe/Kyiv",
        "locked": locked,
        "editable": not locked,
        "lock_start": LOCK_START_LABEL,
        "lock_end": LOCK_END_LABEL,
        "now": dt.isoformat(timespec="seconds"),
        "next_open_at": next_open.isoformat(timespec="seconds") if next_open else "",
        "next_lock_at": (
            ""
            if locked or next_lock is None
            else (
                next_lock.isoformat(timespec="seconds")
                if dt.timetz().replace(tzinfo=None) < LOCK_START
                or dt.timetz().replace(tzinfo=None) >= LOCK_END
                else ""
            )
        ),
        "message": message,
    }
