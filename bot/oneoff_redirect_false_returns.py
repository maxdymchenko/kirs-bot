"""Зняти автозаявки, які насправді були переадресацією НП, і закрити як отримання."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.order_purge import _load_flag, _save_flag

logger = logging.getLogger(__name__)

FLAG = "oneoff_redirect_false_returns_20260921"


def run_redirect_false_returns_fix(storage: AppStorage) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    from bot.np_fulfillment import list_np_clients, repair_redirect_treated_as_return
    from bot.novaposhta import np_tracking_is_redirect
    from bot.returns import STATUS_ACCEPTED, is_auto_return, normalize_return_status

    clients = list_np_clients(storage)
    if not clients:
        return {"ok": False, "done": False, "reason": "no_np_clients"}

    items = storage.list_dropper_return_requests(limit=500)
    extra = storage.get_order_by_number("K-260917-0006")
    if extra and extra.get("id") not in {int(x.get("id") or 0) for x in items}:
        items.append(extra)

    docs: list[dict[str, str]] = []
    by_number: dict[str, dict[str, Any]] = {}
    for order in items:
        payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
        ret = order.get("dropper_return") or payload.get("dropper_return")
        if not is_auto_return(ret):
            continue
        if normalize_return_status((ret or {}).get("status")) == STATUS_ACCEPTED:
            continue
        ttn = str((ret or {}).get("ttn_number") or order.get("ttn_number") or "").strip()
        digits = "".join(ch for ch in ttn if ch.isdigit())
        if len(digits) < 10:
            continue
        docs.append({"DocumentNumber": digits, "Phone": ""})
        by_number[digits] = order

    result: dict[str, Any] = {
        "ok": True,
        "done": True,
        "checked": 0,
        "repaired": [],
        "skipped": 0,
        "errors": [],
    }
    if not docs:
        _save_flag(storage, FLAG, result)
        return result

    rows: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for label, client, _is_primary in clients:
        try:
            rows = client.get_status_documents(docs)
            break
        except Exception as exc:
            last_err = exc
            logger.warning("redirect-fix NP batch failed via «%s»: %s", label, exc)
    else:
        result["ok"] = False
        result["done"] = False
        result["errors"].append(str(last_err or "np_batch_failed"))
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        number = str(row.get("Number") or row.get("DocumentNumber") or "").strip()
        order = by_number.get(number)
        if not order:
            continue
        result["checked"] += 1
        if not np_tracking_is_redirect(row):
            result["skipped"] += 1
            continue
        try:
            repaired = repair_redirect_treated_as_return(storage, order, row)
            if repaired.get("ok"):
                result["repaired"].append(
                    {
                        "order": repaired.get("order_number"),
                        "action": repaired.get("action"),
                        "goods": repaired.get("goods"),
                    }
                )
            else:
                result["skipped"] += 1
        except Exception as exc:
            logger.exception("redirect-fix failed for %s", order.get("order_number"))
            result["errors"].append(f"{order.get('order_number')}: {exc}")

    _save_flag(storage, FLAG, result)
    return result
