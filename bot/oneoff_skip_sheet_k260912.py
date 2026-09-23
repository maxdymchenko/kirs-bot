"""Прибрати тестовий K-260912-0001 з «Заказы» і більше не дзеркалити."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.order_purge import _load_flag, _save_flag

logger = logging.getLogger(__name__)

FLAG = "oneoff_skip_sheet_k260912_0001"
ORDER_NO = "K-260912-0001"


def run_skip_sheet_k260912(storage: AppStorage) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    order = storage.get_order_by_number(ORDER_NO)
    if not order:
        result = {"ok": True, "done": True, "missing": True, "order": ORDER_NO}
        _save_flag(storage, FLAG, result)
        return result

    storage.update_order_flags(int(order["id"]), sheets_sync_status="skip_sheet")
    from bot.orders_sheets import delete_sheet_rows_for_order_numbers

    cleared = delete_sheet_rows_for_order_numbers(storage, [ORDER_NO])
    result: dict[str, Any] = {
        "ok": True,
        "done": True,
        "order": ORDER_NO,
        "cleared_rows": cleared.get("row_numbers") or [],
    }
    _save_flag(storage, FLAG, result)
    logger.info("skip_sheet %s cleared=%s", ORDER_NO, result["cleared_rows"])
    return result
