"""Проводки балансу по факту забрання + умовний (прогнозний) баланс.

Фактичний баланс змінюється лише коли посилку отримано клієнтом:
- наложка по ТТН постачальника → +прибуток;
- оплата з балансу / власна ТТН → −дроп ціна;
- передплата понад дроп → −різниця (якщо була).

Умовний баланс = факт + очікувані проводки по посилках ще в очікуванні/в дорозі.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage

logger = logging.getLogger(__name__)


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def order_should_debit_goods(order: dict[str, Any]) -> bool:
    """Списати дроп-ціну після забрання: оплата з балансу або власна ТТН."""
    if bool(order.get("own_ttn")):
        return True
    return str(order.get("payment_method") or "").strip() == "balance"


def order_should_credit_cod_profit(order: dict[str, Any]) -> bool:
    """Прибуток з наложки — лише ТТН постачальника + COD."""
    if bool(order.get("own_ttn")):
        return False
    return str(order.get("payment_method") or "").strip() == "cod"


def order_prepay_overage(order: dict[str, Any]) -> float:
    """Передплата понад дроп-ціну (COD), що піде в мінус з балансу."""
    if str(order.get("payment_method") or "").strip() != "cod":
        return 0.0
    if bool(order.get("own_ttn")):
        return 0.0
    return max(0.0, round(_money(order.get("prepay")) - _money(order.get("total")), 2))


def goods_debit_amount(order: dict[str, Any]) -> float:
    if not order_should_debit_goods(order):
        return 0.0
    return max(0.0, _money(order.get("total")))


def _payload(order: dict[str, Any]) -> dict[str, Any]:
    p = order.get("payload")
    return p if isinstance(p, dict) else {}


def goods_already_debited(storage: AppStorage, order: dict[str, Any]) -> bool:
    payload = _payload(order)
    if payload.get("goods_debited"):
        return True
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if not dropper_id or not order_number:
        return False
    for row in storage.list_ledger(dropper_id, entry_type="balance_payment", limit=500):
        if str(row.get("related_order_id") or "") == order_number:
            return True
    return False


def prepay_overage_already_posted(storage: AppStorage, order: dict[str, Any]) -> bool:
    payload = _payload(order)
    if payload.get("prepay_overage_posted"):
        return True
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if not dropper_id or not order_number:
        return False
    for row in storage.list_ledger(
        dropper_id, entry_type="prepay_overage_debit", limit=500
    ):
        if str(row.get("related_order_id") or "") == order_number:
            return True
    return False


def pending_balance_delta(storage: AppStorage, order: dict[str, Any]) -> float:
    """
    Очікуваний вплив на баланс, поки посилка в очікуванні/в дорозі
    (або отримана, але проводки ще не зроблено — підстраховка).
    """
    from bot.excel_export import order_history_bucket
    from bot.np_fulfillment import order_cod_profit

    bucket = order_history_bucket(order)
    if bucket == "returns":
        return 0.0
    if bucket not in {"awaiting", "transit", "received"}:
        return 0.0

    payload = _payload(order)
    delta = 0.0

    if order_should_credit_cod_profit(order) and not payload.get("profit_credited"):
        profit = order_cod_profit(order)
        if profit > 0:
            delta += profit

    if order_should_debit_goods(order) and not goods_already_debited(storage, order):
        delta -= goods_debit_amount(order)

    overage = order_prepay_overage(order)
    if overage > 0 and not prepay_overage_already_posted(storage, order):
        delta -= overage

    return round(delta, 2)


def compute_conditional_balance(
    storage: AppStorage,
    dropper_id: int,
    *,
    factual: float | None = None,
    orders: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    bal = storage.get_balance(dropper_id) if factual is None else float(factual)
    items = (
        orders
        if orders is not None
        else storage.list_orders_for_dropper(dropper_id, limit=500)
    )
    pending = 0.0
    for order in items:
        pending += pending_balance_delta(storage, order)
    pending = round(pending, 2)
    return {
        "balance": round(bal, 2),
        "conditional_delta": pending,
        "conditional_balance": round(bal + pending, 2),
    }


def debit_goods_if_needed(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any] | None:
    """Списати дроп-ціну після забрання (balance / own_ttn)."""
    if not order_should_debit_goods(order):
        return None
    if goods_already_debited(storage, order):
        if not _payload(order).get("goods_debited"):
            storage.merge_order_payload(order["id"], {"goods_debited": True})
        return None
    amount = goods_debit_amount(order)
    dropper_id = int(order.get("dropper_id") or 0)
    if amount <= 0 or not dropper_id:
        storage.merge_order_payload(order["id"], {"goods_debited": True, "goods_debit_amount": 0})
        return None
    order_number = str(order.get("order_number") or "")
    entry = storage.add_ledger_entry(
        dropper_id=dropper_id,
        amount=-amount,
        entry_type="balance_payment",
        title=f"Оплата з балансу · {order_number}",
        note="Списання «Дроп ціна» після отримання посилки клієнтом",
        related_order_id=order_number,
    )
    storage.merge_order_payload(
        order["id"],
        {"goods_debited": True, "goods_debit_amount": amount},
    )
    return entry


def debit_prepay_overage_if_needed(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any] | None:
    overage = order_prepay_overage(order)
    if overage <= 0:
        return None
    if prepay_overage_already_posted(storage, order):
        if not _payload(order).get("prepay_overage_posted"):
            storage.merge_order_payload(order["id"], {"prepay_overage_posted": True})
        return None
    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        return None
    order_number = str(order.get("order_number") or "")
    entry = storage.add_ledger_entry(
        dropper_id=dropper_id,
        amount=-overage,
        entry_type="prepay_overage_debit",
        title=f"Передплата понад «Дроп ціна» · {order_number}",
        note="Різниця передплати і суми замовлення (після отримання)",
        related_order_id=order_number,
    )
    storage.merge_order_payload(
        order["id"],
        {"prepay_overage_posted": True, "prepay_overage_amount": overage},
    )
    return entry


def settle_order_on_received(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any]:
    """
    Усі проводки по факту забрання.
    Повертає dict з ключами profit_entry, goods_entry, overage_entry.
    """
    from bot.np_fulfillment import credit_cod_profit_if_needed

    result: dict[str, Any] = {
        "profit_entry": None,
        "goods_entry": None,
        "overage_entry": None,
    }
    try:
        result["profit_entry"] = credit_cod_profit_if_needed(storage, order)
    except Exception:
        logger.exception("credit_cod_profit failed order=%s", order.get("id"))
    order = storage.get_order(int(order["id"])) or order
    try:
        result["goods_entry"] = debit_goods_if_needed(storage, order)
    except Exception:
        logger.exception("debit_goods failed order=%s", order.get("id"))
    order = storage.get_order(int(order["id"])) or order
    try:
        result["overage_entry"] = debit_prepay_overage_if_needed(storage, order)
    except Exception:
        logger.exception("debit_prepay_overage failed order=%s", order.get("id"))

    dropper_id = int(order.get("dropper_id") or 0)
    if dropper_id and (
        result["profit_entry"] or result["goods_entry"] or result["overage_entry"]
    ):
        try:
            from bot.credit_holidays import evaluate_credit_holidays

            dropper = storage.get_dropper_by_id(dropper_id)
            if dropper:
                evaluate_credit_holidays(storage, dropper)
        except Exception:
            logger.exception("evaluate_credit_holidays after settle failed")
    return result
