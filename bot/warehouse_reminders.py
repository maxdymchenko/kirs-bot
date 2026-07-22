"""Нагадування дропперу: 5-й і 7-й день посилки на відділенні (о 10:00 Київ)."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
DAY5 = 5
DAY7 = 7
NOTIFY_HOUR = 10

NotifyFn = Callable[[str, str], Awaitable[None]]


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            # Дати з НП без TZ трактуємо як київський локальний час
            dt = dt.replace(tzinfo=KYIV)
        return dt.astimezone(KYIV)
    except ValueError:
        return None


def days_on_branch(arrived_at: datetime, *, today: date | None = None) -> int:
    """Календарний день на відділенні (день прибуття = 1-й)."""
    arrival_day = arrived_at.astimezone(KYIV).date()
    current = today or datetime.now(KYIV).date()
    return max(1, (current - arrival_day).days + 1)


def format_day5_notice(order: dict[str, Any]) -> str:
    order_no = str(order.get("order_number") or "").strip() or "—"
    ttn = str(order.get("ttn_number") or "").strip() or "—"
    return (
        f"⚠️ Замовлення {order_no}: посилка вже 5-й день на відділенні.\n"
        f"ТТН: {ttn}\n\n"
        "Будь ласка, нагадайте клієнту забрати посилку."
    )


def format_day7_notice(order: dict[str, Any]) -> str:
    order_no = str(order.get("order_number") or "").strip() or "—"
    ttn = str(order.get("ttn_number") or "").strip() or "—"
    return (
        f"⚠️ Замовлення {order_no}: посилка останній (7-й) день на відділенні.\n"
        f"ТТН: {ttn}\n\n"
        "Нагадайте клієнту забрати її сьогодні або оформіть повернення."
    )


def seconds_until_next_notify_hour(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> float:
    """Секунди до наступних 10:00 за Києвом (мін. 30 с, або 0 якщо вже 10:00 і allow)."""
    now = now or datetime.now(KYIV)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KYIV)
    else:
        now = now.astimezone(KYIV)
    if allow_current_hour and now.hour == NOTIFY_HOUR:
        return 0.0
    target = datetime.combine(now.date(), time(NOTIFY_HOUR, 0), tzinfo=KYIV)
    if now >= target:
        target = target + timedelta(days=1)
    return max(30.0, (target - now).total_seconds())


async def run_warehouse_reminders_pass(
    storage: AppStorage,
    notify: NotifyFn,
    *,
    now: datetime | None = None,
    force_hour: bool = False,
) -> dict[str, int]:
    """
    Надсилає по одному повідомленню на 5-й і на 7-й день.
    Зазвичай викликається о ~10:00 Київ; force_hour=True — для тестів.
    """
    now = now or datetime.now(KYIV)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KYIV)
    else:
        now = now.astimezone(KYIV)

    stats = {
        "checked": 0,
        "day5": 0,
        "day7": 0,
        "skipped_hour": 0,
        "skipped_no_date": 0,
        "errors": 0,
    }

    if not force_hour and now.hour != NOTIFY_HOUR:
        stats["skipped_hour"] = 1
        return stats

    today = now.date()
    for order in storage.list_orders_at_warehouse(limit=500):
        stats["checked"] += 1
        payload = order.get("payload") or {}
        arrived = _parse_iso(str(payload.get("np_at_warehouse_at") or ""))
        if not arrived:
            stats["skipped_no_date"] += 1
            continue

        days = days_on_branch(arrived, today=today)
        chat_id = str(order.get("chat_id") or "").strip()
        if not chat_id:
            stats["errors"] += 1
            continue

        try:
            if days >= DAY5 and not payload.get("warehouse_day5_notified_at"):
                await notify(chat_id, format_day5_notice(order))
                storage.merge_order_payload(
                    int(order["id"]),
                    {"warehouse_day5_notified_at": now.isoformat(timespec="seconds")},
                )
                payload = (storage.get_order(int(order["id"])) or order).get("payload") or payload
                stats["day5"] += 1

            if days >= DAY7 and not payload.get("warehouse_day7_notified_at"):
                await notify(chat_id, format_day7_notice(order))
                storage.merge_order_payload(
                    int(order["id"]),
                    {"warehouse_day7_notified_at": now.isoformat(timespec="seconds")},
                )
                stats["day7"] += 1
        except Exception:
            stats["errors"] += 1
            logger.exception(
                "Warehouse reminder failed order_id=%s", order.get("id")
            )

    return stats
