"""ШКІ Укрпошти і миттєве «Отримано» після звірки PDF.

Статуси з API Укрпошти для замовлень не запитуємо: після вдалої накладної
замовлення одразу в «Отримано» і списується з балансу, але лишається
на пакуванні, поки комірник його не відправить.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

STATUS_API = "https://www.ukrposhta.ua/status-tracking/0.0.1/statuses/last/with-not-found"
_BATCH = 50

_DOMESTIC_RE = re.compile(r"^\d{13}$")
_S10_RE = re.compile(r"^[A-Z]{2}\d{9}[A-Z]{2}$")
_CARRIER_CODES = {"ukrposhta", "ukr_poshta", "ukrpost", "up", "укрпошта"}


def status_bearer() -> str:
    return (
        os.getenv("UKRPOSHTA_STATUS_BEARER")
        or os.getenv("UKRPOSHTA_BEARER")
        or ""
    ).strip()


def is_ukrposhta_carrier(raw: str) -> bool:
    text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "")
    if text in _CARRIER_CODES:
        return True
    return "ukrposht" in text or "укрпошт" in text


def sanitize_ukrposhta_barcode(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def is_s10_barcode(value: str) -> bool:
    return bool(_S10_RE.fullmatch(sanitize_ukrposhta_barcode(value)))


def is_domestic_barcode(value: str) -> bool:
    return bool(_DOMESTIC_RE.fullmatch(sanitize_ukrposhta_barcode(value)))


def is_plausible_ukrposhta_barcode(value: str) -> bool:
    text = sanitize_ukrposhta_barcode(value)
    return bool(_DOMESTIC_RE.fullmatch(text) or _S10_RE.fullmatch(text))


def take_ukrposhta_number(raw: str) -> str:
    number = sanitize_ukrposhta_barcode(raw)
    if not is_plausible_ukrposhta_barcode(number):
        raise ValueError(
            "Вкажіть ШКІ Укрпошти: 13 цифр або міжнародний номер на кшталт RA123456785UA"
        )
    return number


def sheet_row_is_ukrposhta(carrier: str, ttn: str) -> bool:
    """Рядок листа: підпис служби або міжнародний ШКІ (S10). 13 цифр без підпису — це НП."""
    if is_ukrposhta_carrier(carrier):
        return True
    return is_s10_barcode(ttn)


def order_ukrposhta_trackable(order: dict[str, Any] | None) -> bool:
    if not order:
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    number = str(order.get("ttn_number") or payload.get("ttn_number") or "")
    carrier = str(payload.get("own_ttn_carrier") or payload.get("carrier") or "")
    if is_s10_barcode(number):
        return True
    return is_ukrposhta_carrier(carrier) and is_plausible_ukrposhta_barcode(number)


def sheet_event_name(event: dict[str, Any] | None) -> str:
    if not isinstance(event, dict):
        return ""
    return str(event.get("eventName") or "").strip()


def map_ukrposhta_status(
    event: str | int | None,
    event_name: str = "",
    *,
    reason_id: str | int | None = None,
    reason: str = "",
) -> str:
    """Внутрішній ttn_status за кодом події Укрпошти."""
    try:
        code = int(str(event or "").strip() or "0")
    except (TypeError, ValueError):
        code = 0
    try:
        reason_n = int(str(reason_id or "0").strip() or "0")
    except (TypeError, ValueError):
        reason_n = 0
    text = f"{reason} {event_name}".casefold()
    handed_to_sender = reason_n == 10 or "відправнику" in text or "отправител" in text
    if code == 41000 and handed_to_sender:
        return "returned"
    if code == 41010:
        return "returned"
    if code in {41000, 48000}:
        return "received"
    if code == 31200:
        if any(word in text for word in ("відмов", "отказ")):
            return "refused"
        return "returned"
    if code in {21700, 21400}:
        return "at_warehouse"
    if code in {10600, 10602, 10603}:
        return "failed"
    if code == 10601:
        return "created"
    if code in {10100, 20700, 20800, 20900, 21500, 31100, 31300, 31400}:
        return "in_transit"
    if any(word in text for word in ("вруч", "доставлен")) and not handed_to_sender:
        return "received"
    if any(word in text for word in ("поверн", "возврат")):
        return "returned"
    if any(word in text for word in ("відмов", "отказ")):
        return "refused"
    if "відділен" in text and any(word in text for word in ("надходжен", "у відділен")):
        return "at_warehouse"
    if code or text.strip():
        return "in_transit"
    return "unknown"


def _pick_event(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict) and (value.get("event") or value.get("eventName") or value.get("barcode")):
        return value
    if isinstance(value, list):
        items = [x for x in value if isinstance(x, dict)]
        if not items:
            return None
        return max(items, key=lambda row: int(row.get("step") or 0))
    return None


def _parse_found(payload: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def _store(event: dict[str, Any] | None, fallback_key: str = "") -> None:
        if not event:
            return
        barcode = sanitize_ukrposhta_barcode(str(event.get("barcode") or fallback_key))
        if barcode:
            result[barcode] = event

    if isinstance(payload, list):
        for item in payload:
            _store(_pick_event(item))
        return result
    if not isinstance(payload, dict):
        return result
    found = payload.get("found")
    if isinstance(found, dict):
        for key, val in found.items():
            _store(_pick_event(val), str(key))
        return result
    if isinstance(found, list):
        for item in found:
            _store(_pick_event(item))
        return result
    _store(_pick_event(payload))
    return result


def fetch_last_statuses(barcodes: list[str]) -> dict[str, dict[str, Any]]:
    """Останній статус за ШКІ. Порожній bearer — попередження і порожній результат."""
    token = status_bearer()
    clean = list(
        dict.fromkeys(
            sanitize_ukrposhta_barcode(raw)
            for raw in barcodes
            if is_plausible_ukrposhta_barcode(raw)
        )
    )
    if not clean:
        return {}
    if not token:
        logger.warning(
            "Ukrposhta tracking skipped: задайте UKRPOSHTA_STATUS_BEARER "
            "(bearer сервісу відстеження)"
        )
        return {}

    out: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(clean), _BATCH):
        chunk = clean[offset : offset + _BATCH]
        req = urllib.request.Request(
            STATUS_API,
            data=json.dumps(chunk).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                logger.warning(
                    "Ukrposhta tracking auth failed (HTTP %s). Перевірте UKRPOSHTA_STATUS_BEARER",
                    exc.code,
                )
                return out
            logger.warning("Ukrposhta tracking HTTP %s for %d barcodes", exc.code, len(chunk))
            continue
        except urllib.error.URLError:
            logger.warning("Ukrposhta tracking network error")
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Ukrposhta tracking returned non-JSON")
            continue
        out.update(_parse_found(payload))
    return out


def _payload(order: dict[str, Any]) -> dict[str, Any]:
    payload = order.get("payload")
    return payload if isinstance(payload, dict) else {}


def order_is_ukrposhta(order: dict[str, Any] | None) -> bool:
    if not order:
        return False
    payload = _payload(order)
    own = bool(order.get("own_ttn") or payload.get("own_ttn"))
    carrier = str(payload.get("own_ttn_carrier") or payload.get("carrier") or "")
    return own and is_ukrposhta_carrier(carrier)


def ukrposhta_pdf_ready(order: dict[str, Any] | None) -> bool:
    """Накладна збіглась або власник зняв hold. Інакше не «Отримано» і без списання."""
    if not order:
        return False
    payload = _payload(order)
    if payload.get("ttn_pdf_hold") is True:
        return False
    if str(order.get("sheets_sync_status") or "") == "hold_pdf":
        return False
    return payload.get("ttn_pdf_ok") is True


def ukrposhta_still_packing(order: dict[str, Any] | None) -> bool:
    """Уже «Отримано», але комірник ще не віддав посилку службі."""
    if not order_is_ukrposhta(order):
        return False
    if str(order.get("status") or "") == "cancelled":
        return False
    if str(order.get("ttn_status") or "") != "received":
        return False
    payload = _payload(order)
    if payload.get("warehouse_left_manually") or payload.get("warehouse_left_via_tracking"):
        return False
    stage = str(order.get("warehouse_stage") or payload.get("warehouse_stage") or "")
    return stage != "shipped"


def _undo_ukrposhta_instant(storage: Any, order: dict[str, Any]) -> None:
    """Повернути списання і реферал, якщо Укрпошта більше не має миттєвого «Отримано»."""
    oid = int(order.get("id") or 0)
    if oid <= 0:
        return
    dropper_id = int(order.get("dropper_id") or 0)
    order_number = str(order.get("order_number") or "").strip()
    if dropper_id and order_number:
        storage.delete_ledger_entry_for_order(
            dropper_id=dropper_id,
            entry_type="balance_payment",
            related_order_id=order_number,
        )
        source = storage.get_dropper_by_id(dropper_id)
        referrer_id = int(getattr(source, "referred_by_dropper_id", 0) or 0) if source else 0
        if referrer_id:
            storage.delete_ledger_entry_for_order(
                dropper_id=referrer_id,
                entry_type="referral_credit",
                related_order_id=order_number,
            )
    if (
        str(order.get("status") or "") != "cancelled"
        and bool(order.get("own_ttn") or _payload(order).get("own_ttn"))
        and str(order.get("ttn_status") or "") == "received"
    ):
        storage.update_order_flags(oid, ttn_status="provided")
    storage.merge_order_payload(
        oid,
        {
            "goods_debited": False,
            "goods_debit_amount": 0,
            "ukrposhta_instant_received": False,
            "ever_received": False,
            "referral_credited": False,
            "referral_amount": 0,
        },
    )


def sync_ukrposhta_settlement(storage: Any, order: dict[str, Any] | None) -> dict[str, Any] | None:
    """Після звірки PDF: Укрпошта → «Отримано» і списання. Інакше відкотити миттєву проводку."""
    if not order or not order.get("id"):
        return order
    latest = storage.get_order(int(order["id"])) or order
    payload = _payload(latest)
    instant = bool(payload.get("ukrposhta_instant_received"))
    ready = (
        order_is_ukrposhta(latest)
        and ukrposhta_pdf_ready(latest)
        and str(latest.get("status") or "") != "cancelled"
    )
    if ready:
        if str(latest.get("ttn_status") or "") != "received" or not instant:
            storage.update_order_flags(int(latest["id"]), ttn_status="received")
            storage.merge_order_payload(
                int(latest["id"]),
                {
                    "ukrposhta_instant_received": True,
                    "ever_received": True,
                    "np_status_text": "",
                },
            )
            latest = storage.get_order(int(latest["id"])) or latest
        from bot.balance_settle import settle_order_on_received

        settle_order_on_received(storage, latest)
        return storage.get_order(int(latest["id"])) or latest
    if instant:
        _undo_ukrposhta_instant(storage, latest)
        return storage.get_order(int(latest["id"])) or latest
    return latest
