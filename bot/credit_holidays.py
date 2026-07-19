"""Кредитні канікули: таймер боргу від 85% ліміту, блок і недільні нагадування."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from bot.accounts import AppStorage, Dropper

logger = logging.getLogger(__name__)

DEBT_TIMER_RATIO = 0.85


def _parse_iso(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def debt_amount(balance: float) -> float:
    """Скільки боргу (додатне), якщо баланс у мінусі."""
    return max(0.0, -float(balance or 0))


def debt_threshold(dropper: Dropper) -> float:
    if not dropper.allow_negative_balance:
        return 0.0
    return max(0.0, float(dropper.negative_balance_limit or 0)) * DEBT_TIMER_RATIO


def evaluate_credit_holidays(
    storage: AppStorage,
    dropper: Dropper,
    balance: float | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Оновлює таймер/блок у БД.
    Таймер стартує, коли борг ≥ 85% ліміту мінусу.
    Повне погашення (баланс ≥ 0) скидає таймер і знімає блок канікул.
    """
    now = now or datetime.now(timezone.utc)
    bal = storage.get_balance(dropper.id) if balance is None else float(balance)
    days_limit = max(0, int(dropper.credit_holidays_days or 0))
    threshold = debt_threshold(dropper)
    debt = debt_amount(bal)

    result: dict[str, Any] = {
        "dropper_id": dropper.id,
        "balance": bal,
        "debt": debt,
        "threshold": threshold,
        "days_limit": days_limit,
        "days_elapsed": 0,
        "days_left": None,
        "blocked": bool(dropper.credit_holidays_blocked),
        "timer_active": False,
        "changed": False,
        "notify_candidate": False,
    }

    # Повне погашення
    if bal >= 0:
        if dropper.credit_debt_started_at or dropper.credit_holidays_blocked:
            storage.update_credit_holidays_state(
                dropper.id,
                credit_debt_started_at=None,
                credit_holidays_blocked=False,
            )
            result["changed"] = True
            result["blocked"] = False
        return result

    # Канікули вимкнені або немає ліміту / мінус не дозволений
    if days_limit <= 0 or threshold <= 0 or not dropper.allow_negative_balance:
        if dropper.credit_debt_started_at or dropper.credit_holidays_blocked:
            storage.update_credit_holidays_state(
                dropper.id,
                credit_debt_started_at=None,
                credit_holidays_blocked=False,
            )
            result["changed"] = True
            result["blocked"] = False
        return result

    started = _parse_iso(dropper.credit_debt_started_at)

    if debt >= threshold:
        result["timer_active"] = True
        if started is None:
            started = now
            storage.update_credit_holidays_state(
                dropper.id,
                credit_debt_started_at=now.isoformat(),
            )
            result["changed"] = True
            dropper = storage.get_dropper_by_id(dropper.id) or dropper

        elapsed = max(0, (now - started).days)
        result["days_elapsed"] = elapsed
        result["days_left"] = max(0, days_limit - elapsed)
        result["notify_candidate"] = True

        if elapsed >= days_limit and not dropper.credit_holidays_blocked:
            storage.update_credit_holidays_state(
                dropper.id,
                credit_holidays_blocked=True,
            )
            result["blocked"] = True
            result["changed"] = True
        else:
            result["blocked"] = bool(dropper.credit_holidays_blocked)
    else:
        # Борг є, але нижче 85% — таймер ще не йде / скидаємо старт
        if dropper.credit_debt_started_at and not dropper.credit_holidays_blocked:
            storage.update_credit_holidays_state(
                dropper.id,
                credit_debt_started_at=None,
            )
            result["changed"] = True
        result["blocked"] = bool(dropper.credit_holidays_blocked)

    return result


def is_orders_blocked(dropper: Dropper) -> bool:
    return bool(dropper.orders_disabled or dropper.credit_holidays_blocked)


def format_sunday_notice(dropper: Dropper, info: dict[str, Any]) -> str:
    company = dropper.company_name
    debt = round(float(info.get("debt") or 0))
    limit = round(float(dropper.negative_balance_limit or 0))
    days_left = info.get("days_left")
    days_limit = int(info.get("days_limit") or 0)
    if info.get("blocked"):
        return (
            f"⛔ {company}: кредитні канікули вичерпано.\n"
            f"Борг ≈ {debt} ₴ (ліміт {limit} ₴).\n"
            f"Передачу замовлень заблоковано, доки борг не буде погашено повністю (баланс ≥ 0)."
        )
    left_txt = str(days_left) if days_left is not None else "—"
    return (
        f"⚠️ Нагадування про кредитні канікули ({company})\n\n"
        f"Борг ≈ {debt} ₴ з ліміту {limit} ₴ "
        f"(таймер з {int(DEBT_TIMER_RATIO * 100)}% ліміту).\n"
        f"Залишилось днів: {left_txt} з {days_limit}.\n"
        f"Якщо борг не погасити повністю — передача замовлень буде заблокована."
    )


async def run_credit_holidays_pass(
    storage: AppStorage,
    notify: Callable[[str, str], Awaitable[None]],
    *,
    force_sunday: bool | None = None,
) -> dict[str, int]:
    """Перевірка всіх дропперів. У неділю — повідомлення в чат дроппера."""
    now = datetime.now(timezone.utc)
    is_sunday = force_sunday if force_sunday is not None else (now.weekday() == 6)
    checked = 0
    blocked = 0
    notified = 0

    for dropper in storage.list_droppers():
        if dropper.status != "active":
            continue
        checked += 1
        info = evaluate_credit_holidays(storage, dropper, now=now)
        if info.get("blocked"):
            blocked += 1

        if not is_sunday or not info.get("notify_candidate"):
            continue

        last = _parse_iso(dropper.credit_last_notified_at)
        if last and (now.date() - last.date()).days < 6:
            continue

        fresh = storage.get_dropper_by_id(dropper.id) or dropper
        text = format_sunday_notice(fresh, info)
        try:
            await notify(fresh.chat_id, text)
            storage.update_credit_holidays_state(
                fresh.id,
                credit_last_notified_at=now.isoformat(),
            )
            notified += 1
        except Exception:
            logger.exception(
                "Не вдалося надіслати credit holidays notice dropper_id=%s",
                fresh.id,
            )

    return {"checked": checked, "blocked": blocked, "notified": notified}
