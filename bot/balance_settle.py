"""Проводки балансу по факту забрання + умовний (прогнозний) баланс.

Фактичний баланс змінюється лише коли посилку отримано клієнтом:
- наложка по ТТН постачальника → +прибуток;
- оплата з балансу / власна ТТН → −дроп ціна;
- передплата понад дроп → −різниця (якщо була);
- реферал запрошувачу → +% від дроп-суми (до отримання лише «умовно»).

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


def split_displayed_balances(
    *,
    total_balance: float,
    referral_earned: float,
    orders_pending: float = 0.0,
    referral_pending: float = 0.0,
) -> dict[str, float]:
    """Розділити загальний ledger: баланс замовлень vs реферальний."""
    total = _money(total_balance)
    referral = _money(referral_earned)
    orders = _money(total - referral)
    orders_pending = _money(orders_pending)
    referral_pending = _money(referral_pending)
    return {
        "orders_balance": orders,
        "orders_conditional_delta": orders_pending,
        "orders_conditional_balance": _money(orders + orders_pending),
        "referral_balance": referral,
        "referral_pending_total": referral_pending,
        "referral_conditional_total": _money(referral + referral_pending),
    }


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


_REFERRAL_UNPOST_FLAG = "defer_referral_until_received_20260919"


def referral_should_post(order: dict[str, Any]) -> bool:
    """Факт на реферальний баланс — лише після отримання клієнтом, не після повернення."""
    from bot.excel_export import order_history_bucket

    if str(order.get("status") or "") == "cancelled":
        return False
    payload = _payload(order)
    if payload.get("return_referral_reversed") or payload.get("return_settled"):
        return False
    return order_history_bucket(order) == "received"


def compute_order_referral_amount(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    source: Any = None,
    referrer: Any = None,
) -> float:
    """Сума рефералу від дроп-ціни замовлення (0, якщо програма не діє)."""
    from datetime import datetime, timezone

    from bot.accounts import _parse_iso_dt

    dropper_id = int(order.get("dropper_id") or 0)
    if source is None and dropper_id:
        source = storage.get_dropper_by_id(dropper_id)
    if not source or not getattr(source, "referred_by_dropper_id", None):
        return 0.0
    if referrer is None:
        referrer = storage.get_dropper_by_id(int(source.referred_by_dropper_id))
    if (
        not referrer
        or not referrer.referral_program_enabled
        or float(referrer.referral_percent or 0) <= 0
    ):
        return 0.0
    expires_raw = str(getattr(source, "referral_expires_at", "") or "").strip()
    if expires_raw:
        expires = _parse_iso_dt(expires_raw)
        if expires and datetime.now(timezone.utc) > expires:
            return 0.0
    total = _money(order.get("total"))
    if total <= 0:
        return 0.0
    return round(total * float(referrer.referral_percent) / 100.0, 2)


def referral_credit_posted(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    referrer_id: int | None = None,
    posted_order_numbers: set[str] | None = None,
) -> bool:
    order_number = str(order.get("order_number") or "").strip()
    if not order_number:
        return False
    if posted_order_numbers is not None:
        return order_number in posted_order_numbers
    payload = _payload(order)
    if payload.get("referral_credited"):
        return True
    ref_id = int(referrer_id or 0)
    if ref_id <= 0:
        source = storage.get_dropper_by_id(int(order.get("dropper_id") or 0))
        ref_id = int(getattr(source, "referred_by_dropper_id", 0) or 0) if source else 0
    if ref_id <= 0:
        return False
    for row in storage.list_ledger(ref_id, entry_type="referral_credit", limit=500):
        if str(row.get("related_order_id") or "") == order_number:
            return float(row.get("amount") or 0) > 0
    return False


def pending_referral_amount(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    source: Any = None,
    referrer: Any = None,
    posted_order_numbers: set[str] | None = None,
) -> float:
    """
    Прогноз рефералу, поки посилка в очікуванні / в дорозі
    (або вже отримана, але проводку ще не зроблено).
    """
    from bot.excel_export import order_history_bucket

    if str(order.get("status") or "") == "cancelled":
        return 0.0
    payload = _payload(order)
    if payload.get("return_referral_reversed") or payload.get("return_settled"):
        return 0.0
    bucket = order_history_bucket(order)
    if bucket not in {"awaiting", "transit", "received"}:
        return 0.0
    ref_id = int(getattr(referrer, "id", 0) or 0) if referrer is not None else None
    if referral_credit_posted(
        storage,
        order,
        referrer_id=ref_id,
        posted_order_numbers=posted_order_numbers,
    ):
        return 0.0
    return compute_order_referral_amount(
        storage, order, source=source, referrer=referrer
    )


def referral_earned_from_rows(rows: list[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        if str(row.get("entry_type") or "") in {"referral_credit", "referral_reversal"}:
            total += float(row.get("amount") or 0)
    return round(total, 2)


def compute_referral_pending_for_referrer(
    storage: AppStorage,
    referrer_id: int,
    *,
    posted_order_numbers: set[str] | None = None,
) -> float:
    referrer = storage.get_dropper_by_id(int(referrer_id))
    if not referrer or not referrer.referral_program_enabled:
        return 0.0
    posted = posted_order_numbers
    if posted is None:
        posted = {
            str(x.get("related_order_id") or "")
            for x in storage.list_ledger(
                int(referrer_id), entry_type="referral_credit", limit=500
            )
            if float(x.get("amount") or 0) > 0
        }
    pending = 0.0
    for source in storage.list_referrals(int(referrer_id)):
        for order in storage.list_orders_for_dropper(source.id, limit=500):
            pending += pending_referral_amount(
                storage,
                order,
                source=source,
                referrer=referrer,
                posted_order_numbers=posted,
            )
    return round(pending, 2)


def accrue_referral_if_received(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any] | None:
    """Провести реферал на баланс запрошувача після отримання посилки."""
    if not referral_should_post(order):
        return None
    if referral_credit_posted(storage, order):
        payload = _payload(order)
        if not payload.get("referral_credited"):
            storage.merge_order_payload(int(order["id"]), {"referral_credited": True})
        return None
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if not dropper_id or not order_number:
        return None
    entry = storage.accrue_referral_from_drop_total(
        source_dropper_id=dropper_id,
        drop_total=_money(order.get("total")),
        order_id=order_number,
    )
    if entry:
        storage.merge_order_payload(
            int(order["id"]),
            {
                "referral_credited": True,
                "referral_amount": round(float(entry.get("amount") or 0), 2),
            },
        )
    return entry


def unpost_premature_referral_credits(storage: AppStorage) -> dict[str, Any]:
    """Зняти з факту реферали по замовленнях, які клієнт ще не забрав."""
    from bot.order_purge import _load_flag, _save_flag

    if _load_flag(storage, _REFERRAL_UNPOST_FLAG):
        return {"ok": True, "skipped": True}
    removed: list[str] = []
    kept = 0
    with storage._connect() as conn:
        rows = conn.execute(
            """
            SELECT id, dropper_id, related_order_id
            FROM balance_ledger
            WHERE entry_type = 'referral_credit' AND amount > 0
            """
        ).fetchall()
    for row in rows:
        order_number = str(row["related_order_id"] or "").strip()
        order = storage.get_order_by_number(order_number) if order_number else None
        if order and (
            referral_should_post(order)
            or _payload(order).get("return_referral_reversed")
        ):
            kept += 1
            continue
        storage.delete_ledger_entry_for_order(
            dropper_id=int(row["dropper_id"]),
            entry_type="referral_credit",
            related_order_id=order_number,
        )
        if order:
            storage.merge_order_payload(
                int(order["id"]),
                {"referral_credited": False},
            )
        if order_number:
            removed.append(order_number)
    result = {
        "ok": True,
        "removed": removed,
        "removed_count": len(removed),
        "kept": kept,
    }
    _save_flag(storage, _REFERRAL_UNPOST_FLAG, result)
    return result


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
    Повертає dict з ключами profit_entry, goods_entry, overage_entry, referral_entry.
    """
    from bot.np_fulfillment import credit_cod_profit_if_needed

    result: dict[str, Any] = {
        "profit_entry": None,
        "goods_entry": None,
        "overage_entry": None,
        "referral_entry": None,
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
    order = storage.get_order(int(order["id"])) or order
    try:
        result["referral_entry"] = accrue_referral_if_received(storage, order)
    except Exception:
        logger.exception("accrue_referral failed order=%s", order.get("id"))

    dropper_id = int(order.get("dropper_id") or 0)
    if dropper_id and (
        result["profit_entry"]
        or result["goods_entry"]
        or result["overage_entry"]
        or result["referral_entry"]
    ):
        try:
            from bot.credit_holidays import evaluate_credit_holidays

            dropper = storage.get_dropper_by_id(dropper_id)
            if dropper:
                evaluate_credit_holidays(storage, dropper)
        except Exception:
            logger.exception("evaluate_credit_holidays after settle failed")
    return result
