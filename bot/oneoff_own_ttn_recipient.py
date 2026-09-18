"""Перезаповнити ПІБ одержувача у власних ТТН, де підставився відправник."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.order_purge import _load_flag, _save_flag
from bot.ttn_pdf_verify import fill_own_ttn_recipient, name_matches_dropper

logger = logging.getLogger(__name__)

FLAG = "oneoff_own_ttn_recipient_not_sender_20260918"


def _recipient_full(order: dict[str, Any]) -> str:
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    rec = payload.get("recipient") if isinstance(payload.get("recipient"), dict) else {}
    return " ".join(
        str(rec.get(k) or "").strip()
        for k in ("last_name", "first_name", "patronymic")
    ).strip()


def _pdf_bytes(order: dict[str, Any]) -> bytes | None:
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    from bot.ttn_store import read_pdf_bytes

    for key in ("ttn_pdf_local_abs", "ttn_pdf_local_path"):
        raw = str(payload.get(key) or "").strip()
        if not raw:
            continue
        try:
            data = read_pdf_bytes(raw)
            if data:
                return data
        except Exception:
            continue
    return None


def run_own_ttn_recipient_sender_fix(storage: AppStorage, *, catalog: Any = None) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    from bot.orders_sheets import sync_order_to_sheet

    fixed: list[str] = []
    cleared: list[str] = []
    skipped = 0
    errors: list[str] = []

    for order in storage.list_orders_for_warehouse(limit=800):
        payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
        if not (order.get("own_ttn") or payload.get("own_ttn")):
            continue
        dropper = None
        try:
            did = int(order.get("dropper_id") or 0)
        except (TypeError, ValueError):
            did = 0
        if did:
            dropper = storage.get_dropper_by_id(did)
        before = _recipient_full(order)
        if before and not name_matches_dropper(before, dropper):
            skipped += 1
            continue
        number = str(order.get("order_number") or order.get("id") or "")
        try:
            saved = fill_own_ttn_recipient(
                storage,
                storage.get_order(int(order["id"])) or order,
                pdf_bytes=_pdf_bytes(order),
            )
            after = _recipient_full(saved or {})
            if after and not name_matches_dropper(after, dropper):
                fixed.append(number)
            elif before and not after:
                cleared.append(number)
            else:
                skipped += 1
                continue
            sync_order_to_sheet(
                storage,
                storage.get_order(int(order["id"])) or saved,
                catalog=catalog,
                full=True,
            )
        except Exception as exc:
            logger.exception("own ttn recipient fix failed order=%s", number)
            errors.append(f"{number}:{exc}")

    result: dict[str, Any] = {
        "ok": not errors,
        "done": not errors,
        "fixed": fixed,
        "cleared": cleared,
        "skipped": skipped,
        "errors": errors,
    }
    _save_flag(storage, FLAG, result)
    logger.info("own ttn recipient-not-sender fix: %s", result)
    return result
