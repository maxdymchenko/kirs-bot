"""Архів отриманих замовлень: мітка власника, без проводок балансу."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.excel_export import order_history_bucket

KYIV = ZoneInfo("Europe/Kyiv")


def _payload(order: dict[str, Any]) -> dict[str, Any]:
    p = order.get("payload")
    return p if isinstance(p, dict) else {}


def _is_sheet_order(order: dict[str, Any]) -> bool:
    return bool(_payload(order).get("sheet_order"))


def can_archive_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "received"


def can_unarchive_order(order: dict[str, Any]) -> bool:
    if _is_sheet_order(order):
        return False
    return order_history_bucket(order) == "archive"


def set_orders_archived(
    storage: AppStorage,
    *,
    dropper_id: int,
    order_ids: list[Any],
    archived: bool,
    actor_user_id: str = "",
    actor_label: str = "Власник",
) -> dict[str, Any]:
    """Позначити отримані Mini App-замовлення як архів / зняти мітку.

    Не змінює ttn_status і не пише в ledger.
    """
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
    if not wanted:
        return {"ok": True, "updated": [], "skipped": 0}

    now = datetime.now(KYIV).isoformat(timespec="seconds")
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
            }
            summary = "Повернуто з архіву в Отримано"
        saved = storage.merge_order_payload(oid, patch)
        if not saved:
            skipped += 1
            continue
        try:
            storage.add_order_change(
                order_id=oid,
                order_number=str(saved.get("order_number") or ""),
                actor_role="owner",
                actor_user_id=str(actor_user_id or "").strip(),
                actor_label=str(actor_label or "Власник").strip() or "Власник",
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
        except Exception:
            pass
        updated.append(saved)
    return {"ok": True, "updated": updated, "skipped": skipped}
