"""Одноразово: K-261009-0002 (Крюпенюкова) → «Отримано».

Власна Rozetka ТТН була підставлена з неправильним префіксом, трекінг не працює.
Посилка вже забрана — ставимо ttn_status=received і робимо проводки.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.order_purge import _dropper_label, _load_flag, _save_flag, find_dropper_by_name
from bot.warehouse import STAGE_SHIPPED

logger = logging.getLogger(__name__)

FLAG = "oneoff_received_k261009_0002"
ORDER_NO = "K-261009-0002"


def run_mark_received_k261009_0002(storage: AppStorage) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    order = storage.get_order_by_number(ORDER_NO)
    if not order:
        logger.warning("%s not found yet", ORDER_NO)
        return {"ok": False, "missing": True, "order": ORDER_NO}

    source = find_dropper_by_name(storage, "крюпенюкова")
    dropper_id = int(order.get("dropper_id") or 0)
    if source and dropper_id and int(source.id) != dropper_id:
        result = {
            "ok": False,
            "done": True,
            "order": ORDER_NO,
            "reason": "dropper_mismatch",
            "order_dropper_id": dropper_id,
            "expected_dropper_id": int(source.id),
            "expected_dropper": _dropper_label(source),
        }
        _save_flag(storage, FLAG, result)
        logger.warning("skip %s: dropper mismatch %s", ORDER_NO, result)
        return result

    oid = int(order["id"])
    payload = dict(order.get("payload") or {})
    prev_ttn = str(order.get("ttn_status") or "").strip()
    prev_stage = str(
        order.get("warehouse_stage") or payload.get("warehouse_stage") or ""
    ).strip()

    ret = payload.get("dropper_return")
    cleared_return = False
    if isinstance(ret, dict) and ret.get("status"):
        from bot.returns import STATUS_ACCEPTED, is_auto_return, normalize_return_status

        if normalize_return_status(ret.get("status")) != STATUS_ACCEPTED:
            if is_auto_return(ret):
                from bot.returns import revert_false_auto_return

                order = (
                    revert_false_auto_return(
                        storage, order, reason="received_manual_k261009_0002"
                    )
                    or order
                )
            else:
                storage.merge_order_payload(
                    oid,
                    {
                        "dropper_return": None,
                        "false_auto_return_cleared_at": None,
                        "manual_return_cleared_reason": "received_manual_k261009_0002",
                    },
                )
            cleared_return = True
            order = storage.get_order(oid) or order
            payload = dict(order.get("payload") or {})

    storage.update_order_flags(
        oid, ttn_status="received", warehouse_stage=STAGE_SHIPPED
    )
    storage.merge_order_payload(
        oid,
        {
            "ever_received": True,
            "warehouse_stage": STAGE_SHIPPED,
            "awaiting_payment": False,
            "owner_archived": False,
            "ttn_pdf_hold": False,
            "received_manual_reason": "owner: посилка отримана, ТТН не трекається",
        },
    )
    order = storage.get_order(oid) or order

    from bot.balance_settle import settle_order_on_received

    settled = settle_order_on_received(storage, order)
    order = storage.get_order(oid) or order

    try:
        storage.add_order_change(
            order_id=oid,
            order_number=ORDER_NO,
            actor_role="system",
            actor_label="Система",
            change_type="tracking",
            summary="Позначено отриманим вручну (ТТН не трекається, посилка забрана)",
            diff=[
                {"field": "ttn_status", "old": prev_ttn, "new": "received"},
                {
                    "field": "warehouse_stage",
                    "old": prev_stage,
                    "new": STAGE_SHIPPED,
                },
            ],
        )
    except Exception:
        logger.exception("change log failed for %s", ORDER_NO)

    try:
        from bot.orders_sheets import sync_order_to_sheet

        order = sync_order_to_sheet(storage, order, full=False) or order
    except Exception:
        logger.exception("sheet sync failed for %s", ORDER_NO)

    result: dict[str, Any] = {
        "ok": True,
        "done": True,
        "order": ORDER_NO,
        "order_id": oid,
        "prev_ttn_status": prev_ttn,
        "ttn_status": str(order.get("ttn_status") or ""),
        "cleared_return": cleared_return,
        "goods_debited": bool(settled.get("goods_entry")),
        "referral": bool(settled.get("referral_entry")),
        "ttn_number": str(order.get("ttn_number") or ""),
    }
    _save_flag(storage, FLAG, result)
    logger.info("marked received %s: %s", ORDER_NO, result)
    return result
