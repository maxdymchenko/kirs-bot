"""Рейтинг викупу замовлень дроппера / клієнта за телефоном."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from bot.accounts import AppStorage, Dropper

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, str], Awaitable[None]]
OwnerNotifyFn = Callable[[str], Any]

TIER_HIGH = "high"
TIER_MID = "mid"
TIER_LOW = "low"

# Авточорний список: стільки незаборів/відмов по номеру
AUTO_BLACKLIST_LOST_THRESHOLD = 5


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


def order_client_phone(order: dict[str, Any]) -> str:
    recipient = (order.get("payload") or {}).get("recipient") or {}
    return AppStorage.normalize_client_phone(str(recipient.get("phone") or ""))


def format_cart_summary(cart: Any) -> str:
    if not isinstance(cart, list):
        return "—"
    parts: list[str] = []
    for item in cart[:10]:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or item.get("title") or "").strip()
        color = str(item.get("color") or "").strip()
        try:
            qty = int(item.get("qty") or item.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        bit = code or name or "товар"
        if color:
            bit = f"{bit} ({color})"
        if qty > 1:
            bit = f"{bit} ×{qty}"
        parts.append(bit)
    return ", ".join(parts) if parts else "—"


def build_client_phone_profile(
    storage: AppStorage,
    phone: str,
    *,
    include_orders: bool = True,
    orders_limit: int = 100,
) -> dict[str, Any]:
    digits = AppStorage.normalize_client_phone(phone)
    orders = (
        storage.list_orders_for_client_phone(digits, limit=500) if digits else []
    )
    stats = compute_buyout(orders)
    result: dict[str, Any] = {
        "phone_digits": digits,
        "phone_display": f"+{digits}" if digits else "",
        "buyout": stats,
        "orders_total": len(orders),
        "blacklisted": bool(digits and storage.is_phone_blacklisted(digits)),
        "orders": [],
    }
    if not include_orders or not digits:
        return result

    limit = max(0, min(int(orders_limit or 100), 200))
    dropper_cache: dict[int, Dropper | None] = {}
    items: list[dict[str, Any]] = []
    for order in orders[:limit]:
        did = int(order.get("dropper_id") or 0)
        if did not in dropper_cache:
            dropper_cache[did] = storage.get_dropper_by_id(did) if did else None
        dropper = dropper_cache[did]
        payload = order.get("payload") or {}
        recipient = payload.get("recipient") or {}
        first = str(recipient.get("first_name") or "").strip()
        last = str(recipient.get("last_name") or "").strip()
        patronymic = str(recipient.get("patronymic") or "").strip()
        client_name = " ".join(p for p in (last, first, patronymic) if p).strip()
        outcome = order_buyout_outcome(order)
        items.append(
            {
                "order_number": order.get("order_number") or "",
                "created_at": order.get("created_at") or "",
                "total": order.get("total"),
                "ttn_status": order.get("ttn_status") or "",
                "ttn_number": order.get("ttn_number") or "",
                "outcome": outcome,
                "dropper_name": (dropper.company_name if dropper else "") or "",
                "dropper_chat_id": (dropper.chat_id if dropper else "") or "",
                "cart_summary": format_cart_summary(payload.get("cart")),
                "client_name": client_name,
            }
        )
    result["orders"] = items
    return result


def format_auto_blacklist_notice(
    phone_digits: str, stats: dict[str, Any]
) -> str:
    percent = stats.get("percent")
    pct_s = f"{percent}%" if percent is not None else "—"
    return (
        "🚫 Авточорний список\n\n"
        f"Номер: +{phone_digits}\n"
        f"Незаборів/відмов: {stats.get('lost', 0)}\n"
        f"Забрано: {stats.get('received', 0)} · "
        f"завершених: {stats.get('completed', 0)}\n"
        f"Викуп: {pct_s}\n\n"
        f"Номер додано автоматично "
        f"(правило: ≥{AUTO_BLACKLIST_LOST_THRESHOLD} незаборів/відмов)."
    )


async def maybe_auto_blacklist_client(
    storage: AppStorage,
    order: dict[str, Any],
    owner_notify: OwnerNotifyFn | None = None,
) -> dict[str, Any] | None:
    """
    Якщо по номеру клієнта ≥ N незаборів/відмов — додати в чорний список
    і повідомити власника (лише при новому записі).
    """
    phone = order_client_phone(order)
    if not phone:
        return None
    if storage.is_phone_blacklisted(phone):
        return None
    orders = storage.list_orders_for_client_phone(phone, limit=500)
    stats = compute_buyout(orders)
    lost = int(stats.get("lost") or 0)
    if lost < AUTO_BLACKLIST_LOST_THRESHOLD:
        return None
    entry, created = storage.try_add_phone_blacklist(
        phone,
        note=f"Авто: {lost} незаборів/відмов",
        created_by_user_id="system",
    )
    if not created or not entry:
        return entry
    if owner_notify:
        try:
            result = owner_notify(format_auto_blacklist_notice(phone, stats))
            if hasattr(result, "__await__"):
                await result
        except Exception:
            logger.exception(
                "auto blacklist owner notify failed phone=%s", phone
            )
    return entry
