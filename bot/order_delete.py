"""Видалення / відновлення замовлення власником (без кабінету НП)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.excel_export import order_is_owner_deleted
from bot.order_edit import clear_ledger_for_cancelled_order

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")

LEDGER_TYPES = (
    "balance_payment",
    "prepay_overage_debit",
    "cod_profit_credit",
    "cod_profit_reversal",
    "return_delivery_debit",
    "return_delivery_reversal",
    "return_goods_credit",
    "referral_credit",
    "referral_reversal",
)


def _now_iso() -> str:
    return datetime.now(KYIV).isoformat(timespec="seconds")


def _payload(order: dict[str, Any] | None) -> dict[str, Any]:
    p = (order or {}).get("payload")
    return dict(p) if isinstance(p, dict) else {}


def _is_sheet_order(order: dict[str, Any] | None) -> bool:
    return bool(_payload(order).get("sheet_order"))


def _save_order(
    storage: AppStorage,
    order: dict[str, Any],
    payload: dict[str, Any],
    *,
    status: str,
    ttn_status: str | None = None,
    sheets_sync_status: str,
) -> dict[str, Any] | None:
    return storage.replace_order(
        int(order["id"]),
        payment_method=str(order.get("payment_method") or ""),
        delivery_method=str(order.get("delivery_method") or ""),
        own_ttn=bool(order.get("own_ttn")),
        total=float(order.get("total") or 0),
        prepay=float(order.get("prepay") or 0),
        prepay_balance_debit=float(order.get("prepay_balance_debit") or 0),
        cod_amount=float(order.get("cod_amount") or 0),
        ttn_number=str(order.get("ttn_number") or ""),
        ttn_status=str(
            ttn_status if ttn_status is not None else order.get("ttn_status") or "none"
        ),
        payload=payload,
        status=str(status or "accepted"),
        sheets_sync_status=str(sheets_sync_status or "pending"),
    )


def _collect_ledger_snapshot(
    storage: AppStorage, order: dict[str, Any]
) -> list[dict[str, Any]]:
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if not dropper_id or not order_number:
        return []
    dropper_ids = {dropper_id}
    source = storage.get_dropper_by_id(dropper_id)
    if source and source.referred_by_dropper_id:
        dropper_ids.add(int(source.referred_by_dropper_id))
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for did in dropper_ids:
        for entry_type in LEDGER_TYPES:
            for row in storage.list_ledger(did, entry_type=entry_type, limit=500):
                if str(row.get("related_order_id") or "").strip() != order_number:
                    continue
                key = (int(row.get("dropper_id") or 0), str(row.get("entry_type") or ""))
                if key in seen:
                    continue
                seen.add(key)
                related = row.get("related_dropper_id")
                try:
                    related_id = int(related) if related is not None and str(related).strip() else None
                except (TypeError, ValueError):
                    related_id = None
                out.append(
                    {
                        "dropper_id": int(row.get("dropper_id") or 0),
                        "amount": float(row.get("amount") or 0),
                        "entry_type": str(row.get("entry_type") or ""),
                        "title": str(row.get("title") or ""),
                        "note": str(row.get("note") or ""),
                        "related_order_id": order_number,
                        "related_dropper_id": related_id,
                        "meta_json": str(row.get("meta_json") or ""),
                    }
                )
    return out


def _restore_ledger_snapshot(
    storage: AppStorage, snapshot: list[dict[str, Any]] | None
) -> None:
    for row in snapshot or []:
        if not isinstance(row, dict):
            continue
        dropper_id = int(row.get("dropper_id") or 0)
        entry_type = str(row.get("entry_type") or "").strip()
        related = str(row.get("related_order_id") or "").strip()
        if not dropper_id or not entry_type or not related:
            continue
        storage.upsert_ledger_entry(
            dropper_id=dropper_id,
            amount=float(row.get("amount") or 0),
            entry_type=entry_type,
            title=str(row.get("title") or ""),
            note=str(row.get("note") or ""),
            related_order_id=related,
            related_dropper_id=row.get("related_dropper_id"),
            meta_json=str(row.get("meta_json") or ""),
        )


def owner_delete_order(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    catalog: Any = None,
    actor_user_id: str = "",
    actor_label: str = "Власник",
) -> dict[str, Any]:
    """М'яке видалення: склад, баланс, червоний порожній рядок у «Заказы». Кабінет НП не чіпає."""
    if not order or not order.get("id"):
        raise ValueError("Замовлення не знайдено")
    if _is_sheet_order(order):
        raise ValueError("Рядок з таблиці «Заказы» так не видаляється")
    if order_is_owner_deleted(order):
        raise ValueError("Замовлення вже видалено")

    payload = _payload(order)
    cart = list(payload.get("cart") or []) if isinstance(payload.get("cart"), list) else []
    stock_already = bool(
        payload.get("stock_restored_on_return")
        or payload.get("stock_restored_on_owner_delete")
    )
    already_cancelled = str(order.get("status") or "") == "cancelled"
    stock_restored = bool(payload.get("stock_restored_on_owner_delete"))
    if cart and catalog is not None and not stock_already and not already_cancelled:
        catalog.restore_cart_stock(cart)
        stock_restored = True
        storage.merge_order_payload(
            int(order["id"]), {"stock_restored_on_owner_delete": True}
        )

    from bot.orders_sheets import blank_deleted_order_rows

    sheet_rows = blank_deleted_order_rows(storage, order)
    if not sheet_rows:
        prev_rows = payload.get("owner_deleted_sheet_rows") or []
        if isinstance(prev_rows, list):
            sheet_rows = prev_rows
    if sheet_rows:
        storage.merge_order_payload(
            int(order["id"]), {"owner_deleted_sheet_rows": sheet_rows}
        )
    ledger_snapshot = _collect_ledger_snapshot(storage, order)
    snapshot = {
        "status": str(order.get("status") or "accepted"),
        "ttn_status": str(order.get("ttn_status") or "none"),
        "warehouse_stage": str(
            order.get("warehouse_stage") or payload.get("warehouse_stage") or ""
        ),
        "sheets_sync_status": str(order.get("sheets_sync_status") or "pending"),
        "sheet_rows": sheet_rows,
        "ledger": ledger_snapshot,
        "stock_restored": stock_restored,
    }

    payload["owner_deleted"] = True
    payload["owner_deleted_at"] = _now_iso()
    payload["owner_deleted_by"] = str(actor_user_id or "").strip()
    payload["owner_deleted_snapshot"] = snapshot
    payload["owner_deleted_sheet_rows"] = sheet_rows
    if stock_restored:
        payload["stock_restored_on_owner_delete"] = True

    saved = _save_order(
        storage,
        order,
        payload,
        status="cancelled",
        sheets_sync_status="skip_sheet",
    )
    clear_ledger_for_cancelled_order(storage, saved or order)
    storage.add_order_change(
        order_id=int(order["id"]),
        order_number=str((saved or order).get("order_number") or ""),
        actor_role="owner",
        actor_user_id=str(actor_user_id or "").strip(),
        actor_label=actor_label or "Власник",
        change_type="status",
        summary="Замовлення видалено власником (кабінет НП не змінювали)",
        diff=[
            {
                "field": "owner_deleted",
                "old": False,
                "new": True,
            }
        ],
    )
    return saved or order


def owner_restore_order(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    catalog: Any = None,
    actor_user_id: str = "",
    actor_label: str = "Власник",
) -> dict[str, Any]:
    """Повернути видалене замовлення: наявність, баланс, рядок у таблиці."""
    if not order or not order.get("id"):
        raise ValueError("Замовлення не знайдено")
    if not order_is_owner_deleted(order):
        raise ValueError("Замовлення не видалене")

    payload = _payload(order)
    snapshot = payload.get("owner_deleted_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    cart = list(payload.get("cart") or []) if isinstance(payload.get("cart"), list) else []
    if (
        snapshot.get("stock_restored")
        and payload.get("stock_restored_on_owner_delete")
        and cart
        and catalog is not None
    ):
        catalog.consume_cart_stock(cart)
        storage.merge_order_payload(
            int(order["id"]), {"stock_restored_on_owner_delete": False}
        )
        payload["stock_restored_on_owner_delete"] = False

    _restore_ledger_snapshot(storage, snapshot.get("ledger") if isinstance(snapshot.get("ledger"), list) else [])

    old_status = str(snapshot.get("status") or "accepted").strip() or "accepted"
    old_ttn = str(snapshot.get("ttn_status") or order.get("ttn_status") or "none")
    orig_sync = str(snapshot.get("sheets_sync_status") or "pending").strip() or "pending"
    stage = str(snapshot.get("warehouse_stage") or "").strip()
    preferred = snapshot.get("sheet_rows") or payload.get("owner_deleted_sheet_rows") or []

    payload.pop("owner_deleted", None)
    payload.pop("owner_deleted_at", None)
    payload.pop("owner_deleted_by", None)
    payload.pop("owner_deleted_snapshot", None)
    payload.pop("owner_deleted_sheet_rows", None)
    payload["stock_restored_on_owner_delete"] = False
    payload["owner_restored_at"] = _now_iso()

    saved = _save_order(
        storage,
        order,
        payload,
        status=old_status,
        ttn_status=old_ttn,
        sheets_sync_status="skip_sheet",
    )
    if stage:
        saved = storage.update_order_flags(int(order["id"]), warehouse_stage=stage) or saved

    if orig_sync != "skip_sheet":
        from bot.orders_sheets import restore_blanked_order_rows

        restore_blanked_order_rows(
            storage,
            saved or order,
            catalog=catalog,
            preferred_rows=list(preferred) if isinstance(preferred, list) else [],
        )
        next_sync = orig_sync if orig_sync in {"hold_pdf", "skip_sheet"} else "ok"
        saved = (
            storage.update_order_flags(
                int(order["id"]), sheets_sync_status=next_sync
            )
            or saved
        )

    storage.add_order_change(
        order_id=int(order["id"]),
        order_number=str((saved or order).get("order_number") or ""),
        actor_role="owner",
        actor_user_id=str(actor_user_id or "").strip(),
        actor_label=actor_label or "Власник",
        change_type="status",
        summary="Замовлення відновлено власником",
        diff=[
            {
                "field": "owner_deleted",
                "old": True,
                "new": False,
            }
        ],
    )
    return storage.get_order(int(order["id"])) or saved or order
