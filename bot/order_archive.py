"""Архів і виставлення рахунку дропперу: мітки власника, без проводок балансу."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.excel_export import order_history_bucket

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")


def _payload(order: dict[str, Any]) -> dict[str, Any]:
    p = order.get("payload")
    return p if isinstance(p, dict) else {}


def _is_sheet_order(order: dict[str, Any]) -> bool:
    return bool(_payload(order).get("sheet_order"))


def _now_iso() -> str:
    return datetime.now(KYIV).isoformat(timespec="seconds")


def _parse_order_ids(order_ids: list[Any] | None) -> list[int]:
    wanted: list[int] = []
    seen: set[int] = set()
    for raw in order_ids or []:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        if oid <= 0 or oid in seen:
            continue
        seen.add(oid)
        wanted.append(oid)
    return wanted


def _fmt_drop_sum(amount: float) -> str:
    return f"{float(amount or 0):.2f}".replace(".", ",")


def settlement_summary(
    orders: list[dict[str, Any]],
    dropper: Any | None = None,
) -> dict[str, Any]:
    total = round(sum(float(o.get("total") or 0) for o in orders), 2)
    name = str(getattr(dropper, "company_name", "") or "").strip() or "дроппер"
    chat_id = str(getattr(dropper, "chat_id", "") or "").strip()
    return {
        "count": len(orders),
        "sum": total,
        "sum_label": _fmt_drop_sum(total),
        "dropper_name": name,
        "dropper_chat_id": chat_id,
    }


def awaiting_payment_tab_tone(orders: list[dict[str, Any]] | None) -> str:
    waiting = [
        o
        for o in (orders or [])
        if order_history_bucket(o) == "awaiting_payment"
    ]
    if not waiting:
        return ""
    if any(not _payload(o).get("dropper_marked_paid") for o in waiting):
        return "alert"
    return "paid"


def can_bill_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "received"


def can_unbill_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "awaiting_payment"


def can_archive_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "awaiting_payment"


def can_unarchive_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "archive"


def _log_change(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    actor_role: str,
    actor_user_id: str,
    actor_label: str,
    change_type: str,
    summary: str,
    diff: list[dict[str, Any]],
) -> None:
    try:
        storage.add_order_change(
            order_id=int(order["id"]),
            order_number=str(order.get("order_number") or ""),
            actor_role=actor_role,
            actor_user_id=str(actor_user_id or "").strip(),
            actor_label=str(actor_label or "").strip() or "Система",
            change_type=change_type,
            summary=summary,
            diff=diff,
        )
    except Exception:
        logger.exception("settlement change log failed for %s", order.get("order_number"))


def set_orders_awaiting_payment(
    storage: AppStorage,
    *,
    dropper_id: int,
    order_ids: list[Any],
    awaiting: bool,
    actor_user_id: str = "",
    actor_label: str = "Власник",
) -> dict[str, Any]:
    """Отримано ↔ Очікує оплату. Архів і таблицю не чіпає."""
    wanted = _parse_order_ids(order_ids)
    empty = {
        "ok": True,
        "updated": [],
        "skipped": 0,
        "awaiting": awaiting,
        **settlement_summary([], storage.get_dropper_by_id(int(dropper_id))),
    }
    if not wanted:
        return empty

    now = _now_iso()
    updated: list[dict[str, Any]] = []
    skipped = 0
    for oid in wanted:
        order = storage.get_order(oid)
        if not order or int(order.get("dropper_id") or 0) != int(dropper_id):
            skipped += 1
            continue
        if awaiting:
            if not can_bill_order(order):
                skipped += 1
                continue
            patch = {
                "awaiting_payment": True,
                "awaiting_payment_at": now,
                "dropper_marked_paid": False,
                "dropper_marked_paid_at": "",
            }
            summary = "Виставлено до оплати"
        else:
            if not can_unbill_order(order):
                skipped += 1
                continue
            patch = {
                "awaiting_payment": False,
                "awaiting_unbilled_at": now,
                "dropper_marked_paid": False,
                "dropper_marked_paid_at": "",
            }
            summary = "Повернуто з очікування оплати в Отримано"
        saved = storage.merge_order_payload(oid, patch)
        if not saved:
            skipped += 1
            continue
        _log_change(
            storage,
            saved,
            actor_role="owner",
            actor_user_id=actor_user_id,
            actor_label=actor_label or "Власник",
            change_type="awaiting_payment",
            summary=summary,
            diff=[
                {
                    "field": "awaiting_payment",
                    "old": (not awaiting),
                    "new": awaiting,
                }
            ],
        )
        updated.append(saved)
    dropper = storage.get_dropper_by_id(int(dropper_id))
    return {
        "ok": True,
        "updated": updated,
        "skipped": skipped,
        "awaiting": awaiting,
        **settlement_summary(updated, dropper),
    }


def mark_orders_paid_by_dropper(
    storage: AppStorage,
    *,
    dropper_id: int,
    actor_user_id: str = "",
    actor_label: str = "Дроппер",
) -> dict[str, Any]:
    """Кнопка «Сплачено»: усі поточні замовлення у вкладці «Очікує оплату»."""
    dropper = storage.get_dropper_by_id(int(dropper_id))
    items = storage.list_orders_for_dropper(int(dropper_id), limit=500)
    waiting = [o for o in items if order_history_bucket(o) == "awaiting_payment"]
    now = _now_iso()
    updated: list[dict[str, Any]] = []
    already = 0
    for order in waiting:
        if _payload(order).get("dropper_marked_paid"):
            already += 1
            continue
        saved = storage.merge_order_payload(
            int(order["id"]),
            {
                "dropper_marked_paid": True,
                "dropper_marked_paid_at": now,
            },
        )
        if not saved:
            continue
        _log_change(
            storage,
            saved,
            actor_role="dropper",
            actor_user_id=actor_user_id,
            actor_label=actor_label or "Дроппер",
            change_type="dropper_paid",
            summary="Дроппер підтвердив оплату",
            diff=[{"field": "dropper_marked_paid", "old": False, "new": True}],
        )
        updated.append(saved)
    all_waiting = [
        storage.get_order(int(o["id"])) or o
        for o in waiting
    ]
    return {
        "ok": True,
        "updated": updated,
        "already": already,
        "skipped": 0,
        **settlement_summary(all_waiting if all_waiting else updated, dropper),
        "tone": awaiting_payment_tab_tone(all_waiting),
    }


def set_orders_archived(
    storage: AppStorage,
    *,
    dropper_id: int,
    order_ids: list[Any],
    archived: bool,
    actor_user_id: str = "",
    actor_label: str = "Власник",
) -> dict[str, Any]:
    """Очікує оплату → архів / зняти архів назад в Отримано.

    Не змінює ttn_status і не пише в ledger.
    """
    wanted = _parse_order_ids(order_ids)
    if not wanted:
        return {"ok": True, "updated": [], "skipped": 0}

    now = _now_iso()
    updated: list[dict[str, Any]] = []
    skipped = 0
    for oid in wanted:
        order = storage.get_order(oid)
        if not order or int(order.get("dropper_id") or 0) != int(dropper_id):
            skipped += 1
            continue
        if archived:
            if not can_archive_order(order):
                skipped += 1
                continue
            patch = {
                "owner_archived": True,
                "owner_archived_at": now,
            }
            summary = "Перенесено в архів"
        else:
            if not can_unarchive_order(order):
                skipped += 1
                continue
            patch = {
                "owner_archived": False,
                "owner_unarchived_at": now,
                "awaiting_payment": False,
                "dropper_marked_paid": False,
                "dropper_marked_paid_at": "",
            }
            summary = "Повернуто з архіву в Отримано"
        saved = storage.merge_order_payload(oid, patch)
        if not saved:
            skipped += 1
            continue
        _log_change(
            storage,
            saved,
            actor_role="owner",
            actor_user_id=actor_user_id,
            actor_label=actor_label or "Власник",
            change_type="archive",
            summary=summary,
            diff=[
                {
                    "field": "owner_archived",
                    "old": (not archived),
                    "new": archived,
                }
            ],
        )
        updated.append(saved)
    if updated:
        try:
            from bot.orders_sheets import sync_archived_settlements_batch

            sync_archived_settlements_batch(
                storage, updated, archived=archived
            )
        except Exception:
            logger.exception("archive sheet Q batch failed")
    return {"ok": True, "updated": updated, "skipped": skipped}


def format_awaiting_payment_notice(summary: dict[str, Any]) -> str:
    name = str(summary.get("dropper_name") or "дроппер")
    count = int(summary.get("count") or 0)
    money = str(summary.get("sum_label") or "0,00")
    return (
        f"💸 Виставлено до оплати · {name}\n"
        f"{count} замовлень, дроп {money} ₴\n"
        f"Вкладка Mini App: «Очікує оплату»\n\n"
        "Потрібно звірити суму і провести розрахунок."
    )


def format_dropper_paid_notice(summary: dict[str, Any]) -> str:
    name = str(summary.get("dropper_name") or "дроппер")
    count = int(summary.get("count") or 0)
    money = str(summary.get("sum_label") or "0,00")
    return (
        f"✅ Дроппер підтвердив оплату · {name}\n"
        f"{count} замовлень, дроп {money} ₴\n"
        f"Вкладка Mini App: «Очікує оплату»\n\n"
        "Дроппер підтвердив суму і зазначив, що оплатив. "
        "Перевірте рахунок і перенесіть замовлення в архів."
    )
