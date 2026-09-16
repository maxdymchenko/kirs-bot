"""Одноразово: суми в «Заказы» = ціна × кількість, жовтий фон якщо qty>1."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.order_purge import _load_flag, _save_flag
from bot.orders_sheets import (
    _qty_int,
    paint_qty_column_from_sheet,
    sync_order_to_sheet,
)

logger = logging.getLogger(__name__)

FLAG = "oneoff_sheet_qty_line_totals_20260916"


def _cart_has_qty_gt1(order: dict[str, Any]) -> bool:
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    cart = payload.get("cart") if isinstance(payload.get("cart"), list) else []
    for item in cart:
        if isinstance(item, dict) and _qty_int(item.get("qty")) > 1:
            return True
    return False


def run_qty_line_totals_fix(storage: AppStorage, *, catalog: Any = None) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    synced: list[str] = []
    errors: list[str] = []
    orders = storage.list_orders_for_warehouse(limit=800)
    for order in orders:
        if not _cart_has_qty_gt1(order):
            continue
        number = str(order.get("order_number") or order.get("id") or "")
        try:
            saved = sync_order_to_sheet(storage, order, catalog=catalog, full=True)
            status = str((saved or order).get("sheets_sync_status") or "")
            if status == "synced":
                synced.append(number)
            else:
                errors.append(f"{number}:{status or 'unknown'}")
        except Exception as exc:
            logger.exception("qty line-totals sync failed order=%s", number)
            errors.append(f"{number}:{exc}")

    painted = 0
    paint_error = ""
    try:
        from bot.orders_sheets import _open_orders_worksheet

        ws = _open_orders_worksheet(storage)
        painted = paint_qty_column_from_sheet(ws)
    except Exception as exc:
        logger.exception("qty highlight scan failed")
        paint_error = str(exc)

    result: dict[str, Any] = {
        "ok": not errors and not paint_error,
        "done": not errors and not paint_error,
        "synced": synced,
        "synced_count": len(synced),
        "errors": errors,
        "painted_qty_gt1": painted,
        "paint_error": paint_error,
    }
    _save_flag(storage, FLAG, result)
    logger.info("qty line-totals fix: %s", result)
    return result
