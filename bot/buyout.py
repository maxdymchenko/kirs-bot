"""Рейтинг викупу замовлень дроппера."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from bot.accounts import AppStorage, Dropper

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, str], Awaitable[None]]

TIER_HIGH = "high"
TIER_MID = "mid"
TIER_LOW = "low"


def order_buyout_outcome(order: dict[str, Any]) -> str | None:
    """
    'received' | 'lost' | None (ще не фінальний).
    Враховуємо лише завершені доставки.
    """
    ttn = str(order.get("ttn_status") or "").strip()
    payload = order.get("payload") or {}
    if ttn == "received":
        return "received"
    if ttn in {"refused", "returned", "return_at_warehouse"}:
        return "lost"
    if payload.get("return_after_received") or payload.get("dropper_return"):
        return "lost"
    if payload.get("ever_received") and ttn not in {
        "in_transit",
        "at_warehouse",
        "created",
        "pending_create",
        "provided",
        "none",
        "create_error",
    }:
        return "received"
    return None


def compute_buyout(orders: list[dict[str, Any]]) -> dict[str, Any]:
    received = 0
    lost = 0
    for order in orders:
        outcome = order_buyout_outcome(order)
        if outcome == "received":
            received += 1
        elif outcome == "lost":
            lost += 1
    completed = received + lost
    percent: float | None
    if completed <= 0:
        percent = None
        tier = ""
    else:
        percent = round(100.0 * received / completed, 1)
        if percent >= 80.0:
            tier = TIER_HIGH
        elif percent >= 60.0:
            tier = TIER_MID
        else:
            tier = TIER_LOW
    return {
        "received": received,
        "lost": lost,
        "completed": completed,
        "percent": percent,
        "tier": tier,
        "label": tier_label(tier, percent),
        "force_full_payment": percent is not None and percent <= 50.0,
    }


def tier_label(tier: str, percent: float | None) -> str:
    if percent is None or not tier:
        return ""
    if tier == TIER_HIGH:
        return "Високий рейтинг викупу замовлень"
    if tier == TIER_MID:
        return "Середній рейтинг викупу замовлень"
    if tier == TIER_LOW:
        return "Низький рейтинг викупу замовлень"
    return ""


def format_tier_change_notice(company: str, percent: float, tier: str) -> str:
    label = tier_label(tier, percent)
    return (
        f"📊 Рейтинг викупу оновлено ({company})\n\n"
        f"Поточний викуп: {percent}%\n"
        f"{label}"
    )


def format_half_rating_warning(company: str, percent: float) -> str:
    return (
        f"⚠️ Увага: рейтинг викупу {percent}% ({company})\n\n"
        "Відправка можлива лише при повній оплаті.\n"
        "У разі відмови клієнта стягується плата в розмірі вартості "
        "доставки у зворотний бік + 50 ₴ утримується як збитки."
    )


async def evaluate_dropper_buyout(
    storage: AppStorage,
    dropper: Dropper,
    notify: NotifyFn | None = None,
) -> dict[str, Any]:
    orders = storage.list_orders_for_dropper(dropper.id, limit=500)
    stats = compute_buyout(orders)
    percent = stats["percent"]
    tier = stats["tier"]

    prev_notified = str(getattr(dropper, "buyout_tier_notified", "") or "")
    half_warned = bool(getattr(dropper, "buyout_half_warned", False))

    storage.update_buyout_state(
        dropper.id,
        buyout_percent=percent,
        buyout_tier=tier,
    )

    # Повідомлення при зміні статусу рейтингу (один раз на новий tier)
    if notify and tier and percent is not None and tier != prev_notified:
        try:
            await notify(
                dropper.chat_id,
                format_tier_change_notice(dropper.company_name, percent, tier),
            )
            storage.update_buyout_state(dropper.id, buyout_tier_notified=tier)
        except Exception:
            logger.exception(
                "buyout tier notify failed dropper_id=%s", dropper.id
            )

    # Окреме попередження при ≤50%
    if notify and percent is not None and percent <= 50.0 and not half_warned:
        try:
            await notify(
                dropper.chat_id,
                format_half_rating_warning(dropper.company_name, percent),
            )
            storage.update_buyout_state(dropper.id, buyout_half_warned=True)
        except Exception:
            logger.exception(
                "buyout half warn failed dropper_id=%s", dropper.id
            )
    elif percent is not None and percent > 50.0 and half_warned:
        storage.update_buyout_state(dropper.id, buyout_half_warned=False)

    stats["dropper_id"] = dropper.id
    return stats


async def evaluate_all_buyouts(
    storage: AppStorage, notify: NotifyFn | None = None
) -> dict[str, int]:
    checked = 0
    for dropper in storage.list_droppers():
        if dropper.status != "active":
            continue
        checked += 1
        try:
            await evaluate_dropper_buyout(storage, dropper, notify=notify)
        except Exception:
            logger.exception("buyout eval failed dropper_id=%s", dropper.id)
    return {"checked": checked}
