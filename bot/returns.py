"""Заявки дроппера на повернення товару після отримання клієнтом."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Callable

from bot.accounts import AppStorage
from bot.novaposhta import map_np_status_code

logger = logging.getLogger(__name__)

OwnerNotifyFn = Callable[[str], Any]
NotifyFn = Callable[[str, str], Any]

STATUS_AWAITING_RECEIPT = "awaiting_receipt"
STATUS_AWAITING_CONFIRM = "awaiting_confirm"
STATUS_ACCEPTED = "accepted"

# Старі значення → нові
_STATUS_ALIASES = {
    "pending": STATUS_AWAITING_RECEIPT,
    "closed": STATUS_ACCEPTED,
}

BUCKET_AWAITING_RECEIPT = "awaiting_receipt"
BUCKET_AWAITING_CONFIRM = "awaiting_confirm"
BUCKET_CLOSED = "closed"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_return_status(status: str | None) -> str:
    raw = str(status or "").strip().lower()
    if not raw:
        return STATUS_AWAITING_RECEIPT
    return _STATUS_ALIASES.get(raw, raw)


def return_bucket(ret: dict[str, Any] | None) -> str:
    if not isinstance(ret, dict):
        return BUCKET_AWAITING_RECEIPT
    st = normalize_return_status(ret.get("status"))
    if st == STATUS_ACCEPTED:
        return BUCKET_CLOSED
    if st == STATUS_AWAITING_CONFIRM:
        return BUCKET_AWAITING_CONFIRM
    return BUCKET_AWAITING_RECEIPT


def status_label_uk(status: str | None) -> str:
    st = normalize_return_status(status)
    if st == STATUS_ACCEPTED:
        return "Закрито"
    if st == STATUS_AWAITING_CONFIRM:
        return "Очікує підтвердження"
    return "Очікує отримання"


ORIGIN_MANUAL = "manual"
ORIGIN_AUTO = "auto"
TYPE_AUTO_CARRIER = "auto_carrier"

RETURN_TYPE_LABELS = {
    "easy": "Ручне повернення від клієнта",
    "regular": "Ручне повернення від клієнта",
    TYPE_AUTO_CARRIER: "Відмова / повернення перевізником",
}


def is_auto_return(ret: dict[str, Any] | None) -> bool:
    if not isinstance(ret, dict):
        return False
    origin = str(ret.get("origin") or "").strip().lower()
    rtype = str(ret.get("type") or "").strip().lower()
    return origin == ORIGIN_AUTO or rtype == TYPE_AUTO_CARRIER


def return_type_label(ret: dict[str, Any] | None) -> str:
    if is_auto_return(ret):
        return RETURN_TYPE_LABELS[TYPE_AUTO_CARRIER]
    rtype = str((ret or {}).get("type") or "").strip().lower()
    return RETURN_TYPE_LABELS.get(rtype, "Ручне повернення від клієнта")


def is_trackable_return_ttn(ttn: str) -> bool:
    raw = str(ttn or "").strip().upper()
    if raw.startswith("RMP-") or raw.startswith("PRM-"):
        return False
    digits = re.sub(r"\D", "", raw)
    return len(digits) >= 10


def ttn_search_digits(ttn: str) -> str:
    return re.sub(r"\D", "", str(ttn or ""))


def return_matches_ttn_query(order: dict[str, Any], query: str) -> bool:
    """Пошук за останніми 5 цифрами зворотної або оригінальної ТТН."""
    needle = ttn_search_digits(query)
    if not needle:
        return True
    tail = needle[-5:]
    ret = order.get("dropper_return")
    if not isinstance(ret, dict):
        payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
        ret = payload.get("dropper_return") if isinstance(payload.get("dropper_return"), dict) else {}
    candidates = [
        str((ret or {}).get("ttn_number") or ""),
        str(order.get("ttn_number") or ""),
        str((order.get("payload") or {}).get("ttn_number") or "")
        if isinstance(order.get("payload"), dict)
        else "",
    ]
    return any(
        ttn_search_digits(raw).endswith(tail)
        for raw in candidates
        if ttn_search_digits(raw)
    )


def return_tab_sort_ts(ret: dict[str, Any] | None, bucket: str) -> str:
    if not isinstance(ret, dict):
        return ""
    if bucket == BUCKET_CLOSED:
        return str(
            ret.get("accepted_at")
            or ret.get("entered_confirm_at")
            or ret.get("created_at")
            or ""
        )
    if bucket == BUCKET_AWAITING_CONFIRM:
        return str(
            ret.get("entered_confirm_at")
            or ret.get("received_at")
            or ret.get("created_at")
            or ""
        )
    return str(ret.get("entered_receipt_at") or ret.get("created_at") or "")


def new_dropper_return(
    *,
    return_type: str,
    ttn_number: str,
    origin: str = ORIGIN_MANUAL,
    status: str = STATUS_AWAITING_RECEIPT,
) -> dict[str, Any]:
    now = _now_iso()
    origin_key = ORIGIN_AUTO if str(origin).strip().lower() == ORIGIN_AUTO else ORIGIN_MANUAL
    st = normalize_return_status(status)
    row = {
        "type": return_type,
        "origin": origin_key,
        "ttn_number": ttn_number,
        "status": st,
        "ttn_status": "",
        "created_at": now,
        "entered_receipt_at": now,
        "entered_confirm_at": now if st == STATUS_AWAITING_CONFIRM else "",
        "received_at": now if st == STATUS_AWAITING_CONFIRM else "",
        "accepted_at": "",
        "accepted_by": "",
        "refund_amount": 0,
        "settled": False,
    }
    return row


def _should_auto_return(order: dict[str, Any]) -> bool:
    if str(order.get("status") or "") == "cancelled":
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    if payload.get("return_after_received"):
        return False
    ttn = str(order.get("ttn_status") or "").strip()
    return ttn in {"refused", "returned", "return_at_warehouse"}


def ensure_auto_return(
    storage: AppStorage, order: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Створити заявку на повернення з відмови/повернення перевізника (та сама ТТН)."""
    if not order or not order.get("id"):
        return order
    payload = dict(order.get("payload") or {})
    existing = payload.get("dropper_return")
    if isinstance(existing, dict) and existing.get("status"):
        return order
    if not _should_auto_return(order):
        return order
    ttn_status = str(order.get("ttn_status") or "").strip()
    ttn_number = str(
        order.get("ttn_number") or payload.get("ttn_number") or ""
    ).strip()
    if not ttn_number:
        return order
    at_our_wh = ttn_status == "return_at_warehouse"
    created = new_dropper_return(
        return_type=TYPE_AUTO_CARRIER,
        ttn_number=ttn_number,
        origin=ORIGIN_AUTO,
        status=STATUS_AWAITING_CONFIRM if at_our_wh else STATUS_AWAITING_RECEIPT,
    )
    created["ttn_status"] = ttn_status
    saved = storage.merge_order_payload(int(order["id"]), {"dropper_return": created})
    try:
        storage.add_order_change(
            order_id=int(order["id"]),
            order_number=str(order.get("order_number") or ""),
            actor_role="system",
            actor_label="Перевізник",
            change_type="tracking",
            summary="Відмова/повернення перевізника — заявка в «Повернення»",
            diff=[
                {
                    "field": "dropper_return.origin",
                    "old": "",
                    "new": ORIGIN_AUTO,
                }
            ],
        )
    except Exception:
        logger.exception("auto return change log failed")
    return saved or order


def backfill_auto_returns(
    storage: AppStorage, *, dropper_id: int | None = None, limit: int = 400
) -> int:
    created = 0
    orders = storage.list_orders_for_auto_return_backfill(
        dropper_id=dropper_id, limit=limit
    )
    for order in orders:
        before = (order.get("payload") or {}).get("dropper_return")
        if isinstance(before, dict) and before.get("status"):
            continue
        if not _should_auto_return(order):
            continue
        saved = ensure_auto_return(storage, order)
        after = ((saved or {}).get("payload") or {}).get("dropper_return")
        if isinstance(after, dict) and after.get("status"):
            created += 1
    return created


def mapped_closes_auto_return(mapped: str) -> bool:
    """ТТН отримано на нашому відділенні / видано нам."""
    return str(mapped or "").strip() in {"received", "return_at_warehouse"}


async def mark_return_received_async(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    ttn_status: str = "received",
    actor_role: str = "system",
    actor_label: str = "Нова Пошта",
    actor_user_id: str = "",
    owner_notify: OwnerNotifyFn | None = None,
) -> dict[str, Any] | None:
    payload = order.get("payload") or {}
    ret = payload.get("dropper_return")
    if not isinstance(ret, dict):
        return None
    st = normalize_return_status(ret.get("status"))
    if st == STATUS_ACCEPTED:
        return order

    updated = dict(ret)
    prev = normalize_return_status(ret.get("status"))
    updated["status"] = STATUS_AWAITING_CONFIRM
    updated["ttn_status"] = str(ttn_status or "received")
    now = _now_iso()
    if not updated.get("received_at"):
        updated["received_at"] = now
    if not updated.get("entered_confirm_at"):
        updated["entered_confirm_at"] = now

    saved = storage.merge_order_payload(int(order["id"]), {"dropper_return": updated})
    if prev != STATUS_AWAITING_CONFIRM:
        try:
            storage.add_order_change(
                order_id=int(order["id"]),
                order_number=str(order.get("order_number") or ""),
                actor_role=actor_role,
                actor_user_id=actor_user_id,
                actor_label=actor_label,
                change_type="tracking",
                summary="Зворотну ТТН отримано — очікує підтвердження власника",
                diff=[
                    {
                        "field": "dropper_return.status",
                        "old": prev,
                        "new": STATUS_AWAITING_CONFIRM,
                    }
                ],
            )
        except Exception:
            logger.exception("return received change log failed")

        if owner_notify:
            dropper = storage.get_dropper_by_id(int(order.get("dropper_id") or 0))
            text = (
                "📦 Повернення прибуло\n\n"
                f"Замовлення: {order.get('order_number')}\n"
                f"Дроппер: {(dropper.company_name if dropper else '') or '—'}\n"
                f"ТТН повернення: {updated.get('ttn_number') or '—'}\n"
                "Статус: очікує підтвердження в кабінеті → «Повернення»."
            )
            try:
                result = owner_notify(text)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception("return received owner notify failed")

    return saved or order


def settle_confirmed_return(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    accepted_by: str = "",
) -> dict[str, Any]:
    """
    Підтвердження власником:
    - сторно прибутку з наложки (якщо був);
    - нарахування дроп-ціни (товар) на баланс дроппера;
    - сторно рефералу (якщо був);
    - статус accepted + прапорці settled.
    """
    payload = dict(order.get("payload") or {})
    ret = payload.get("dropper_return")
    if not isinstance(ret, dict) or not ret.get("status"):
        raise ValueError("Немає заявки на повернення")

    st = normalize_return_status(ret.get("status"))
    if st == STATUS_ACCEPTED:
        return {"order": order, "already": True, "refund_amount": float(ret.get("refund_amount") or 0)}
    if st != STATUS_AWAITING_CONFIRM:
        raise ValueError(
            "Підтвердити можна лише після отримання зворотної посилки "
            "(вкладка «Очікують підтвердження»)"
        )

    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        raise ValueError("Немає дроппера в замовленні")

    order_number = str(order.get("order_number") or "")
    total = round(max(0.0, float(order.get("total") or 0)), 2)
    ledger_notes: list[str] = []

    # 1) Сторно прибутку з наложки
    if payload.get("profit_credited") and not payload.get("profit_reversed"):
        profit = round(float(payload.get("profit_amount") or 0), 2)
        if profit > 0:
            entry = storage.add_ledger_entry(
                dropper_id=dropper_id,
                amount=-profit,
                entry_type="cod_profit_reversal",
                title=f"Сторно прибутку (повернення товару) · {order_number}",
                note="Повернення підтверджено власником — продаж скасовано",
                related_order_id=order_number,
            )
            if entry:
                ledger_notes.append(f"сторно прибутку −{profit} ₴")
            payload["profit_reversed"] = True
            payload["profit_credited"] = False

    # 2) Повернення дроп-ціни на баланс:
    #    — якщо раніше списували з балансу після забрання, АБО
    #    — якщо дроппер платив одразу на реквізити (гроші поза балансом → повертаємо на баланс)
    refund = 0.0
    payment = str(order.get("payment_method") or "").strip()
    goods_was_debited = bool(payload.get("goods_debited"))
    if not goods_was_debited:
        # Legacy: була проводка balance_payment до нової моделі
        existing_debit = next(
            (
                x
                for x in storage.list_ledger(
                    dropper_id=dropper_id, entry_type="balance_payment", limit=500
                )
                if str(x.get("related_order_id") or "") == order_number
                and float(x.get("amount") or 0) < 0
            ),
            None,
        )
        goods_was_debited = existing_debit is not None

    paid_via_requisites = payment == "requisites"
    should_refund_goods = goods_was_debited or paid_via_requisites

    if total > 0 and should_refund_goods and not payload.get("return_goods_credited"):
        note = (
            "Повернення оплати на реквізити — нарахування дроп-ціни на баланс"
            if paid_via_requisites and not goods_was_debited
            else "Нарахування дроп-ціни після підтвердження повернення власником"
        )
        entry = storage.add_ledger_entry(
            dropper_id=dropper_id,
            amount=total,
            entry_type="return_goods_credit",
            title=f"Повернення товару · {order_number}",
            note=note,
            related_order_id=order_number,
        )
        if entry:
            refund = total
            ledger_notes.append(f"товар +{total} ₴")
            payload["return_goods_credited"] = True
            payload["return_goods_amount"] = total
            if paid_via_requisites and not goods_was_debited:
                payload["return_requisites_refund"] = True

    # 3) Сторно рефералу (якщо нараховували з цього замовлення)
    if not payload.get("return_referral_reversed"):
        source = storage.get_dropper_by_id(dropper_id)
        ref_id = int(getattr(source, "referred_by_dropper_id", 0) or 0) if source else 0
        if ref_id:
            existing = next(
                (
                    x
                    for x in storage.list_ledger(
                        dropper_id=ref_id, entry_type="referral_credit", limit=500
                    )
                    if str(x.get("related_order_id") or "") == order_number
                    and float(x.get("amount") or 0) > 0
                ),
                None,
            )
            if existing:
                amt = round(float(existing["amount"]), 2)
                storage.add_ledger_entry(
                    dropper_id=ref_id,
                    amount=-amt,
                    entry_type="referral_reversal",
                    title=f"Сторно рефералу (повернення) · {order_number}",
                    note="Повернення товару підтверджено",
                    related_order_id=order_number,
                    related_dropper_id=dropper_id,
                )
                ledger_notes.append(f"сторно реф. −{amt} ₴")
                payload["return_referral_reversed"] = True

    now = _now_iso()
    updated_ret = dict(ret)
    updated_ret["status"] = STATUS_ACCEPTED
    updated_ret["accepted_at"] = now
    updated_ret["accepted_by"] = str(accepted_by or "").strip()
    updated_ret["settled"] = True
    updated_ret["refund_amount"] = refund or float(ret.get("refund_amount") or total or 0)
    if not updated_ret.get("received_at"):
        updated_ret["received_at"] = now
    if not updated_ret.get("entered_confirm_at"):
        updated_ret["entered_confirm_at"] = now

    payload["dropper_return"] = updated_ret
    payload["return_settled"] = True
    payload["return_settled_at"] = now

    saved = storage.merge_order_payload(int(order["id"]), payload)
    storage.add_order_change(
        order_id=int(order["id"]),
        order_number=order_number,
        actor_role="owner",
        actor_user_id=str(accepted_by or "").strip(),
        actor_label="Власник",
        change_type="status",
        summary="Повернення підтверджено"
        + (f" ({', '.join(ledger_notes)})" if ledger_notes else ""),
        diff=[
            {
                "field": "dropper_return.status",
                "old": st,
                "new": STATUS_ACCEPTED,
            }
        ],
    )
    return {
        "order": saved or storage.get_order(int(order["id"])) or order,
        "already": False,
        "refund_amount": float(updated_ret.get("refund_amount") or 0),
        "ledger_notes": ledger_notes,
    }


async def track_return_ttns_async(
    storage: AppStorage,
    *,
    owner_notify: OwnerNotifyFn | None = None,
) -> dict[str, int]:
    """Опитування статусів зворотних ТТН заявок на повернення."""
    from bot.np_fulfillment import list_np_clients

    stats = {"checked": 0, "moved": 0, "errors": 0, "auto_created": 0}
    try:
        stats["auto_created"] = backfill_auto_returns(storage, limit=400)
    except Exception:
        logger.exception("auto-return backfill failed")
    clients = list_np_clients(storage)
    if not clients:
        return stats

    items = storage.list_dropper_return_requests(limit=250)
    docs: list[dict[str, str]] = []
    by_number: dict[str, dict[str, Any]] = {}
    for order in items:
        ret = order.get("dropper_return") or {}
        if normalize_return_status(ret.get("status")) != STATUS_AWAITING_RECEIPT:
            continue
        ttn = str(ret.get("ttn_number") or "").strip()
        if not is_trackable_return_ttn(ttn):
            continue
        digits = re.sub(r"\D", "", ttn)
        docs.append({"DocumentNumber": digits, "Phone": ""})
        by_number[digits] = order

    if not docs:
        return stats

    rows: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for label, client, _is_primary in clients:
        try:
            rows = client.get_status_documents(docs)
            break
        except Exception as exc:
            last_err = exc
            logger.warning("NP return-TTN batch failed via «%s»: %s", label, exc)
    else:
        logger.error("NP return-TTN batch failed: %s", last_err)
        stats["errors"] += 1
        return stats

    for row in rows:
        number = str(row.get("Number") or row.get("DocumentNumber") or "").strip()
        order = by_number.get(number)
        if not order:
            continue
        stats["checked"] += 1
        mapped = map_np_status_code(
            row.get("StatusCode"), str(row.get("Status") or "")
        )
        # Оновити проміжний статус у заявці
        ret = dict(order.get("dropper_return") or {})
        auto = is_auto_return(ret)
        should_close = (
            mapped_closes_auto_return(mapped)
            if auto
            else mapped in {"received", "at_warehouse", "return_at_warehouse"}
        )
        if str(ret.get("ttn_status") or "") != mapped:
            ret["ttn_status"] = mapped
            storage.merge_order_payload(
                int(order["id"]), {"dropper_return": ret}
            )
            order = storage.get_order(int(order["id"])) or order

        if should_close:
            full = storage.get_order(int(order["id"])) or order
            before_ret = (full.get("payload") or {}).get("dropper_return") or {}
            before = normalize_return_status(before_ret.get("status"))
            await mark_return_received_async(
                storage,
                full,
                ttn_status=mapped,
                owner_notify=owner_notify,
            )
            after_order = storage.get_order(int(order["id"])) or full
            after_ret = (after_order.get("payload") or {}).get("dropper_return") or {}
            if (
                normalize_return_status(after_ret.get("status"))
                == STATUS_AWAITING_CONFIRM
                and before != STATUS_AWAITING_CONFIRM
            ):
                stats["moved"] += 1

    return stats
