"""Допоміжні функції редагування замовлення власником: diff, ledger, snapshot."""

from __future__ import annotations

import json
import logging
from typing import Any

from bot.accounts import AppStorage
from bot.np_fulfillment import order_cod_profit

logger = logging.getLogger(__name__)


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value).strip()


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _cart_fingerprint(cart: list[dict] | None) -> str:
    rows = []
    for item in cart or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "code": _s(item.get("code")),
                "name": _s(item.get("name")),
                "color": _s(item.get("color")),
                "qty": int(item.get("qty") or 1),
                "drop_price": _s(item.get("drop_price")),
                "product_id": _s(item.get("product_id")),
            }
        )
    rows.sort(key=lambda x: (x["code"], x["color"], x["product_id"]))
    return json.dumps(rows, ensure_ascii=False, sort_keys=True)


def compute_order_diff(old: dict[str, Any], new_snap: dict[str, Any]) -> list[dict[str, str]]:
    """Порівняти старе замовлення і новий знімок → список {field, old, new}."""
    diffs: list[dict[str, str]] = []

    def add(field: str, old_v: Any, new_v: Any) -> None:
        o, n = _s(old_v), _s(new_v)
        if o != n:
            diffs.append({"field": field, "old": o, "new": n})

    old_p = old.get("payload") or {}
    old_r = old_p.get("recipient") or {}
    old_d = old_p.get("delivery") or {}
    new_r = new_snap.get("recipient") or {}
    new_d = new_snap.get("delivery") or {}

    add("payment_method", old.get("payment_method"), new_snap.get("payment_method"))
    add("delivery_method", old.get("delivery_method"), new_snap.get("delivery_method"))
    add("own_ttn", bool(old.get("own_ttn")), bool(new_snap.get("own_ttn")))
    add("total", _money(old.get("total")), _money(new_snap.get("total")))
    add("prepay", _money(old.get("prepay")), _money(new_snap.get("prepay")))
    add(
        "prepay_balance_debit",
        _money(old.get("prepay_balance_debit")),
        _money(new_snap.get("prepay_balance_debit")),
    )
    add("cod_amount", _money(old.get("cod_amount")), _money(new_snap.get("cod_amount")))
    add("ttn_number", old.get("ttn_number") or old_p.get("ttn_number"), new_snap.get("ttn_number"))
    add("comment", old_p.get("comment"), new_snap.get("comment"))
    add("own_ttn_carrier", old_p.get("own_ttn_carrier"), new_snap.get("own_ttn_carrier"))

    for key, label in (
        ("last_name", "last_name"),
        ("first_name", "first_name"),
        ("patronymic", "patronymic"),
        ("phone", "phone"),
    ):
        add(f"recipient.{label}", old_r.get(key), new_r.get(key))

    for key in (
        "city",
        "city_ref",
        "warehouse",
        "warehouse_ref",
        "street",
        "street_ref",
        "house",
        "apartment",
    ):
        add(f"delivery.{key}", old_d.get(key), new_d.get(key))

    old_cart_fp = _cart_fingerprint(old_p.get("cart") if isinstance(old_p.get("cart"), list) else [])
    new_cart_fp = _cart_fingerprint(new_snap.get("cart") if isinstance(new_snap.get("cart"), list) else [])
    if old_cart_fp != new_cart_fp:
        diffs.append(
            {
                "field": "cart",
                "old": old_cart_fp[:400],
                "new": new_cart_fp[:400],
            }
        )
    return diffs


def summarize_diffs(diffs: list[dict[str, str]], limit: int = 12) -> str:
    labels = {
        "payment_method": "Оплата",
        "delivery_method": "Доставка",
        "own_ttn": "Власна ТТН",
        "total": "Дроп ціна",
        "prepay": "Передплата",
        "prepay_balance_debit": "Списання з балансу",
        "cod_amount": "Накладний платіж",
        "ttn_number": "ТТН",
        "comment": "Коментар",
        "cart": "Склад замовлення",
        "recipient.phone": "Телефон",
        "recipient.first_name": "Імʼя",
        "recipient.last_name": "Прізвище",
        "recipient.patronymic": "По батькові",
        "delivery.city": "Місто",
        "delivery.warehouse": "Відділення",
        "delivery.street": "Вулиця",
        "delivery.house": "Будинок",
        "delivery.apartment": "Квартира",
    }
    lines = []
    for d in diffs[:limit]:
        field = d.get("field") or ""
        label = labels.get(field, field)
        if field == "cart":
            lines.append(f"• {label}: змінено")
        else:
            lines.append(f"• {label}: {d.get('old') or '—'} → {d.get('new') or '—'}")
    if len(diffs) > limit:
        lines.append(f"• … ще {len(diffs) - limit} змін")
    return "\n".join(lines)


def sync_ledger_for_edited_order(storage: AppStorage, order: dict[str, Any]) -> None:
    """Перезаписати ledger-записи, привʼязані до order_number."""
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if not dropper_id or not order_number:
        return

    payment = str(order.get("payment_method") or "").strip()
    debit = _money(order.get("prepay_balance_debit"))
    total = _money(order.get("total"))
    payload = order.get("payload") or {}

    # Списання з балансу / передплата понад дроп
    if payment == "balance" and debit > 0:
        storage.upsert_ledger_entry(
            dropper_id=dropper_id,
            amount=-debit,
            entry_type="balance_payment",
            title=f"Оплата з балансу · {order_number}",
            note="Списання суми «Дроп ціна» з балансу дроппера (після редагування)",
            related_order_id=order_number,
        )
        storage.delete_ledger_entry_for_order(
            dropper_id=dropper_id,
            entry_type="prepay_overage_debit",
            related_order_id=order_number,
        )
    elif debit > 0 and payment != "balance":
        storage.upsert_ledger_entry(
            dropper_id=dropper_id,
            amount=-debit,
            entry_type="prepay_overage_debit",
            title=f"Передплата понад «Дроп ціна» · {order_number}",
            note="Різниця передплати і суми замовлення (після редагування)",
            related_order_id=order_number,
        )
        storage.delete_ledger_entry_for_order(
            dropper_id=dropper_id,
            entry_type="balance_payment",
            related_order_id=order_number,
        )
    else:
        storage.delete_ledger_entry_for_order(
            dropper_id=dropper_id,
            entry_type="balance_payment",
            related_order_id=order_number,
        )
        storage.delete_ledger_entry_for_order(
            dropper_id=dropper_id,
            entry_type="prepay_overage_debit",
            related_order_id=order_number,
        )

    # Реферал — на баланс запрошувача
    source = storage.get_dropper_by_id(dropper_id)
    if source and source.referred_by_dropper_id:
        referrer = storage.get_dropper_by_id(source.referred_by_dropper_id)
        if (
            referrer
            and referrer.referral_program_enabled
            and float(referrer.referral_percent or 0) > 0
            and total > 0
        ):
            amount = round(total * float(referrer.referral_percent) / 100.0, 2)
            storage.upsert_ledger_entry(
                dropper_id=referrer.id,
                amount=amount,
                entry_type="referral_credit",
                title=f"Реферал від {source.company_name}",
                note=(
                    f"{referrer.referral_percent}% від дроп-суми {total:.2f} ₴ "
                    f"(заказ {order_number}, після редагування)"
                ),
                related_order_id=order_number,
                related_dropper_id=source.id,
                meta_json=(
                    f'{{"drop_total":{total},"percent":{float(referrer.referral_percent)},'
                    f'"source_dropper_id":{source.id}}}'
                ),
            )
        elif referrer:
            storage.delete_ledger_entry_for_order(
                dropper_id=referrer.id,
                entry_type="referral_credit",
                related_order_id=order_number,
            )

    # Прибуток з наложки — лише якщо вже був нарахований
    if payload.get("profit_credited") and not payload.get("profit_reversed"):
        profit = order_cod_profit(order)
        if profit > 0:
            storage.upsert_ledger_entry(
                dropper_id=dropper_id,
                amount=profit,
                entry_type="cod_profit_credit",
                title=f"Прибуток з наложки · {order_number}",
                note=(
                    f"Накладний {_money(order.get('cod_amount'))} ₴ − "
                    f"передплата {_money(order.get('prepay'))} ₴ − "
                    f"«Дроп ціна» {total} ₴ (після редагування)"
                ),
                related_order_id=order_number,
            )
            storage.merge_order_payload(
                int(order["id"]),
                {"profit_amount": profit},
            )
        else:
            storage.delete_ledger_entry_for_order(
                dropper_id=dropper_id,
                entry_type="cod_profit_credit",
                related_order_id=order_number,
            )
            storage.merge_order_payload(
                int(order["id"]),
                {"profit_credited": False, "profit_amount": 0},
            )

    # Списання доставки при поверненні — оновити суму якщо вже було
    if payload.get("return_delivery_debited"):
        cost = _money(
            payload.get("return_delivery_cost") or payload.get("np_delivery_cost") or 0
        )
        if cost > 0:
            storage.upsert_ledger_entry(
                dropper_id=dropper_id,
                amount=-cost,
                entry_type="return_delivery_debit",
                title=f"Доставка при поверненні · {order_number}",
                note="Вартість доставки після редагування замовлення",
                related_order_id=order_number,
            )


def build_payload_from_edit(
    *,
    old_payload: dict[str, Any],
    recipient: dict[str, Any],
    delivery: dict[str, Any],
    payment: dict[str, Any],
    cart: list[dict],
    comment: str,
    own_ttn: bool,
    own_ttn_carrier: str,
    ttn_number: str,
    ttn_pdf_name: str = "",
) -> dict[str, Any]:
    """Новий payload зі збереженням системних ключів (tracking, np_*, flags)."""
    keep_keys = (
        "tracking_events",
        "np_document_ref",
        "np_recipient_ref",
        "np_contact_recipient_ref",
        "np_status_code",
        "np_status_text",
        "np_tracked_at",
        "np_at_warehouse_at",
        "np_delivery_cost",
        "np_cost_on_site",
        "np_estimated_delivery_date",
        "np_api_key_label",
        "np_used_backup_key",
        "np_backup_owner_notified",
        "np_error",
        "profit_credited",
        "profit_amount",
        "profit_reversed",
        "return_delivery_debited",
        "return_delivery_cost",
        "ever_received",
        "return_after_received",
        "warehouse_day5_notified",
        "warehouse_day7_notified",
        "created_by_user_id",
        "edited_by_owner",
        "old_ttn_before_recreate",
    )
    payload = {k: old_payload[k] for k in keep_keys if k in old_payload}
    payload.update(
        {
            "recipient": recipient,
            "delivery": delivery,
            "payment": payment,
            "own_ttn": own_ttn,
            "own_ttn_carrier": own_ttn_carrier,
            "ttn_number": ttn_number,
            "ttn_pdf_name": ttn_pdf_name or old_payload.get("ttn_pdf_name") or "",
            "comment": comment,
            "cart": cart,
            "edited_by_owner": True,
        }
    )
    return payload


def enrich_orders_with_changes(
    storage: AppStorage, items: list[dict[str, Any]], limit_per_order: int = 40
) -> list[dict[str, Any]]:
    ids = [int(o["id"]) for o in items if o.get("id")]
    by_id = storage.list_order_changes_for_orders(ids, limit_per_order=limit_per_order)
    out = []
    for order in items:
        row = dict(order)
        row["changes"] = by_id.get(int(order["id"]), []) if order.get("id") else []
        out.append(row)
    return out
