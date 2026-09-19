"""Одноразово: Крюпенюкова → оплата з балансу + реферал Качан."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage, _now
from bot.order_purge import (
    _dropper_label,
    _load_flag,
    _save_flag,
    find_dropper_by_name,
)

logger = logging.getLogger(__name__)

FLAG = "oneoff_kryupenyukova_balance_ref_20260916"
FLAG_0008 = "oneoff_kryupenyukova_0008_balance_20260919"
PAYMENT_ORDERS = (
    "K-260916-0001",
    "K-260916-0002",
    "K-260916-0003",
)
ORDER_0008 = "K-260916-0008"
# Отримані замовлення, які мають бути оплатою з балансу: 257+680+780 = 1717
RECEIVED_BALANCE_ORDERS = (
    "K-260916-0001",
    "K-260916-0003",
    ORDER_0008,
)
REFERRAL_ORDERS = (
    *PAYMENT_ORDERS,
    "K-260916-0004",
    ORDER_0008,
)


def _set_payment_balance(storage: AppStorage, order: dict[str, Any]) -> dict[str, Any]:
    oid = int(order["id"])
    total = round(float(order.get("total") or 0), 2)
    payload = dict(order.get("payload") or {})
    payment = dict(payload.get("payment") or {})
    payment["method"] = "balance"
    with storage._connect() as conn:
        conn.execute(
            "UPDATE orders SET payment_method = ?, updated_at = ? WHERE id = ?",
            ("balance", _now(), oid),
        )
        conn.commit()
    saved = storage.merge_order_payload(
        oid,
        {
            "payment": payment,
            "pending_balance_debit": total,
            "pending_balance_debit_method": "balance",
        },
    )
    return saved or storage.get_order(oid) or order


def _accrue_referral(
    storage: AppStorage,
    *,
    source,
    referrer,
    order: dict[str, Any],
) -> dict[str, Any] | None:
    total = round(float(order.get("total") or 0), 2)
    if total <= 0:
        return None
    percent = float(referrer.referral_percent or 0)
    if percent <= 0:
        return None
    amount = round(total * percent / 100.0, 2)
    if amount <= 0:
        return None
    number = str(order.get("order_number") or "").strip()
    return storage.upsert_ledger_entry(
        dropper_id=referrer.id,
        amount=amount,
        entry_type="referral_credit",
        title=f"Реферал від {source.company_name}",
        note=f"{percent}% від дроп-суми {total:.2f} ₴ (заказ {number})",
        related_order_id=number,
        related_dropper_id=source.id,
        meta_json=(
            f'{{"drop_total":{total},"percent":{percent},'
            f'"source_dropper_id":{int(source.id)}}}'
        ),
    )


def run_kryupenyukova_balance_referral_fix(storage: AppStorage) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    source = find_dropper_by_name(storage, "крюпенюкова")
    referrer = find_dropper_by_name(storage, "качан")
    if not source:
        return {"ok": False, "error": "Дроппера «Крюпенюкова» не знайдено"}
    if not referrer:
        return {"ok": False, "error": "Дроппера «Качан» не знайдено"}

    if int(source.referred_by_dropper_id or 0) != int(referrer.id):
        try:
            storage.assign_dropper_referrer(
                referred_dropper_id=source.id,
                referrer_dropper_id=referrer.id,
            )
            source = storage.get_dropper_by_id(source.id) or source
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Не вдалося привʼязати реферала: {exc}",
                "source": _dropper_label(source),
                "referrer": _dropper_label(referrer),
            }

    payment_changed: list[str] = []
    referral_posted: list[str] = []
    skipped: list[dict[str, str]] = []
    sheet_errors: list[str] = []

    for number in PAYMENT_ORDERS:
        order = storage.get_order_by_number(number)
        if not order:
            skipped.append({"order": number, "reason": "немає в базі"})
            continue
        if int(order.get("dropper_id") or 0) != int(source.id):
            skipped.append({"order": number, "reason": "інший дроппер"})
            continue
        order = _set_payment_balance(storage, order)
        payment_changed.append(number)
        try:
            from bot.orders_sheets import sync_order_to_sheet

            sync_order_to_sheet(storage, order, full=True)
        except Exception as exc:
            logger.exception("kryupenyukova oneoff: sheet sync failed %s", number)
            sheet_errors.append(f"{number}: {exc}")

    for number in REFERRAL_ORDERS:
        order = storage.get_order_by_number(number)
        if not order:
            if number not in PAYMENT_ORDERS:
                skipped.append({"order": number, "reason": "немає в базі"})
            continue
        if int(order.get("dropper_id") or 0) != int(source.id):
            continue
        from bot.balance_settle import accrue_referral_if_received

        entry = accrue_referral_if_received(storage, order)
        if entry:
            referral_posted.append(number)

    result = {
        "ok": not sheet_errors,
        "done": not sheet_errors,
        "source": _dropper_label(source),
        "referrer": _dropper_label(referrer),
        "payment_changed": payment_changed,
        "referral_posted": referral_posted,
        "skipped": skipped,
        "sheet_errors": sheet_errors,
    }
    _save_flag(storage, FLAG, result)
    return result


def run_kryupenyukova_0008_balance_fix(storage: AppStorage) -> dict[str, Any]:
    """0001/0003/0008: оплата з балансу + списання дроп-ціни по вже отриманих."""
    prev = _load_flag(storage, FLAG_0008)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    source = find_dropper_by_name(storage, "крюпенюкова")
    if not source:
        return {"ok": False, "error": "Дроппера «Крюпенюкова» не знайдено"}

    from bot.balance_settle import (
        accrue_referral_if_received,
        debit_goods_if_needed,
        goods_already_debited,
    )
    from bot.excel_export import order_history_bucket

    orders_out: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    sheet_errors: list[str] = []

    for number in RECEIVED_BALANCE_ORDERS:
        order = storage.get_order_by_number(number)
        if not order:
            skipped.append({"order": number, "reason": "немає в базі"})
            continue
        if int(order.get("dropper_id") or 0) != int(source.id):
            skipped.append({"order": number, "reason": "інший дроппер"})
            continue

        order = _set_payment_balance(storage, order)
        goods_entry = None
        referral_entry = None
        if order_history_bucket(order) == "received":
            goods_entry = debit_goods_if_needed(storage, order)
            order = storage.get_order(int(order["id"])) or order
            referral_entry = accrue_referral_if_received(storage, order)
            order = storage.get_order(int(order["id"])) or order

        try:
            from bot.orders_sheets import sync_order_to_sheet

            sync_order_to_sheet(storage, order, full=True)
        except Exception as exc:
            logger.exception("kryupenyukova received-balance: sheet sync failed %s", number)
            sheet_errors.append(f"{number}: {exc}")

        payload = order.get("payload") or {}
        orders_out.append(
            {
                "order": number,
                "total": round(float(order.get("total") or 0), 2),
                "payment_method": order.get("payment_method"),
                "bucket": order_history_bucket(order),
                "goods_debited": goods_already_debited(storage, order)
                or bool(payload.get("goods_debited")),
                "goods_entry_amount": (
                    round(float(goods_entry.get("amount") or 0), 2)
                    if goods_entry
                    else None
                ),
                "referral_posted": bool(referral_entry),
            }
        )

    result = {
        "ok": not sheet_errors and not skipped,
        "done": not sheet_errors and not skipped,
        "source": _dropper_label(source),
        "orders_balance": storage.get_balance(source.id),
        "orders": orders_out,
        "skipped": skipped,
        "sheet_errors": sheet_errors,
    }
    _save_flag(storage, FLAG_0008, result)
    return result
