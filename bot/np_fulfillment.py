"""Створення ТТН Нової Пошти та трекінг до «отримано» + нарахування прибутку."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Callable

from bot.accounts import AppStorage
from bot.novaposhta import NovaPoshtaClient, NovaPoshtaError, map_np_status_code

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, str], Any]

TERMINAL_TTN_STATUSES = frozenset(
    {"received", "returned", "failed", "provided", "cancelled"}
)


def _digits_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("0") and len(digits) == 10:
        digits = "38" + digits
    if digits.startswith("380") and len(digits) >= 12:
        return digits[:12]
    return digits


def resolve_np_client(storage: AppStorage) -> NovaPoshtaClient | None:
    keys = storage.get_enabled_np_api_keys()
    if keys:
        return NovaPoshtaClient(str(keys[0].get("api_key") or "").strip())
    client = NovaPoshtaClient()
    return client if client.configured() else None


def _pick_sender_bundle(client: NovaPoshtaClient, settings: dict[str, Any]) -> dict[str, str]:
    senders = client.get_counterparties("Sender")
    if not senders:
        raise NovaPoshtaError("У кабінеті НП немає контрагента-відправника")
    sender = senders[0]
    sender_ref = str(sender.get("Ref") or "").strip()
    contacts = client.get_counterparty_contact_persons(sender_ref)
    if not contacts:
        raise NovaPoshtaError("Немає контактної особи відправника в НП")
    contact = contacts[0]
    contact_ref = str(contact.get("Ref") or "").strip()
    phone = _digits_phone(contact.get("Phones") or contact.get("Phone") or "")
    if not phone:
        raise NovaPoshtaError("У контакта відправника НП немає телефону")

    wanted_addr = str((settings.get("sender_warehouse") or {}).get("ref") or "").strip()
    addresses = client.get_counterparty_addresses(sender_ref, "Sender")
    address_ref = ""
    if wanted_addr:
        for row in addresses:
            if str(row.get("Ref") or "").strip() == wanted_addr:
                address_ref = wanted_addr
                break
    if not address_ref and addresses:
        address_ref = str(addresses[0].get("Ref") or "").strip()
    if not address_ref and wanted_addr:
        # Іноді в налаштуваннях збережено Ref відділення (AddressGeneral), а не Counterparty address
        address_ref = wanted_addr
    if not address_ref:
        raise NovaPoshtaError("Немає адреси відправника (відділення) у налаштуваннях/НП")

    city_sender = str((settings.get("sender_city") or {}).get("city_ref") or "").strip()
    if not city_sender:
        city_sender = str(sender.get("City") or addresses[0].get("CityRef") or "").strip()
    if not city_sender:
        raise NovaPoshtaError("Не вказано місто відправника в налаштуваннях НП")

    return {
        "sender_ref": sender_ref,
        "contact_ref": contact_ref,
        "phone": phone,
        "address_ref": address_ref,
        "city_sender": city_sender,
    }


def _ensure_recipient_refs(
    client: NovaPoshtaClient, order: dict[str, Any]
) -> tuple[str, str]:
    """Створити/повернути Recipient + ContactRecipient Ref."""
    payload = order.get("payload") or {}
    recipient = payload.get("recipient") or {}
    phone = _digits_phone(recipient.get("phone") or "")
    last_name = str(recipient.get("last_name") or "").strip() or "Отримувач"
    first_name = str(recipient.get("first_name") or "").strip() or "Клієнт"
    middle_name = str(recipient.get("patronymic") or "").strip()
    props = {
        "FirstName": first_name,
        "MiddleName": middle_name,
        "LastName": last_name,
        "Phone": phone,
        "Email": "",
        "CounterpartyType": "PrivatePerson",
        "CounterpartyProperty": "Recipient",
    }
    data = client._request("Counterparty", "save", props) or []
    if not data or not isinstance(data[0], dict):
        raise NovaPoshtaError("Не вдалося створити отримувача в НП")
    row = data[0]
    recipient_ref = str(row.get("Ref") or "").strip()
    contact_ref = str(row.get("ContactPerson", {}).get("Ref") or "").strip()
    if not contact_ref:
        # інколи ContactPerson — рядок/список
        cp = row.get("ContactPerson")
        if isinstance(cp, list) and cp:
            contact_ref = str((cp[0] or {}).get("Ref") or "").strip()
        elif isinstance(cp, str):
            contact_ref = cp.strip()
    if not recipient_ref:
        raise NovaPoshtaError("НП не повернула Ref отримувача")
    if not contact_ref:
        contacts = client.get_counterparty_contact_persons(recipient_ref)
        if contacts:
            contact_ref = str(contacts[0].get("Ref") or "").strip()
    if not contact_ref:
        raise NovaPoshtaError("НП не повернула ContactRecipient")
    return recipient_ref, contact_ref


def _build_save_props(
    order: dict[str, Any],
    settings: dict[str, Any],
    sender: dict[str, str],
    recipient_ref: str,
    contact_recipient_ref: str,
) -> dict[str, Any]:
    payload = order.get("payload") or {}
    delivery = payload.get("delivery") or {}
    recipient = payload.get("recipient") or {}
    parcel = settings.get("parcel_defaults") or {}

    method = str(order.get("delivery_method") or delivery.get("method") or "")
    city_recipient = str(delivery.get("city_ref") or "").strip()
    if not city_recipient:
        np_city = delivery.get("np_city") or {}
        city_recipient = str(np_city.get("city_ref") or "").strip()
    if not city_recipient:
        raise NovaPoshtaError("У замовленні немає city_ref отримувача")

    weight = float(parcel.get("weight_kg") or 0.5) or 0.5
    seats = max(1, int(parcel.get("seats_amount") or 1))
    description = str(parcel.get("description") or "Товар").strip() or "Товар"
    length = float(parcel.get("length_cm") or 30)
    width = float(parcel.get("width_cm") or 20)
    height = float(parcel.get("height_cm") or 10)
    volume = max(0.0001, (length * width * height) / 1_000_000.0)

    cost = max(1.0, float(order.get("total") or 0))
    phone = _digits_phone(recipient.get("phone") or "")
    if len(phone) < 12:
        raise NovaPoshtaError("Некоректний телефон отримувача для ТТН")

    today = datetime.now().strftime("%d.%m.%Y")
    props: dict[str, Any] = {
        "PayerType": "Recipient",
        "PaymentMethod": "Cash",
        "DateTime": today,
        "CargoType": "Parcel",
        "Weight": str(round(weight, 3)),
        "ServiceType": "WarehouseWarehouse",
        "SeatsAmount": str(seats),
        "Description": description[:100],
        "Cost": str(int(round(cost))),
        "CitySender": sender["city_sender"],
        "Sender": sender["sender_ref"],
        "SenderAddress": sender["address_ref"],
        "ContactSender": sender["contact_ref"],
        "SendersPhone": sender["phone"],
        "CityRecipient": city_recipient,
        "Recipient": recipient_ref,
        "ContactRecipient": contact_recipient_ref,
        "RecipientsPhone": phone,
        "OptionsSeat": [
            {
                "volumetricVolume": str(round(volume, 4)),
                "volumetricWidth": str(width),
                "volumetricLength": str(length),
                "volumetricHeight": str(height),
                "weight": str(round(weight, 3)),
            }
        ],
    }

    if method == "np_courier":
        street_ref = str(delivery.get("street_ref") or "").strip()
        house = str(delivery.get("house") or "").strip()
        apartment = str(delivery.get("apartment") or "").strip()
        if not street_ref or not house:
            raise NovaPoshtaError("Для курʼєра потрібні вулиця і будинок")
        props["ServiceType"] = "WarehouseDoors"
        props["RecipientAddress"] = street_ref
        props["RecipientHouse"] = house
        if apartment:
            props["RecipientFlat"] = apartment
    else:
        warehouse_ref = str(delivery.get("warehouse_ref") or "").strip()
        if not warehouse_ref:
            np_wh = delivery.get("np_warehouse") or {}
            warehouse_ref = str(np_wh.get("ref") or "").strip()
        if not warehouse_ref:
            raise NovaPoshtaError("Немає warehouse_ref отримувача")
        props["ServiceType"] = "WarehouseWarehouse"
        props["RecipientAddress"] = warehouse_ref

    cod_amount = max(0.0, float(order.get("cod_amount") or 0))
    if str(order.get("payment_method") or "") == "cod" and cod_amount > 0:
        props["BackwardDeliveryData"] = [
            {
                "PayerType": "Recipient",
                "CargoType": "Money",
                "RedeliveryString": str(int(round(cod_amount))),
            }
        ]

    return props


def create_ttn_for_order(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any]:
    if order.get("own_ttn"):
        return order
    status = str(order.get("ttn_status") or "")
    if status not in {"pending_create", "create_error", "none"}:
        return order
    if order.get("ttn_number"):
        return order

    client = resolve_np_client(storage)
    if not client:
        storage.update_order_flags(order["id"], ttn_status="create_error")
        storage.merge_order_payload(
            order["id"],
            {"np_error": "Немає увімкненого API-ключа Нової Пошти"},
        )
        raise NovaPoshtaError("Немає увімкненого API-ключа Нової Пошти")

    settings = storage.get_general_settings()
    sender = _pick_sender_bundle(client, settings)
    recipient_ref, contact_ref = _ensure_recipient_refs(client, order)
    props = _build_save_props(order, settings, sender, recipient_ref, contact_ref)
    result = client.create_internet_document(props)

    storage.update_order_flags(
        order["id"],
        ttn_number=result["ttn_number"],
        ttn_status="created",
    )
    storage.merge_order_payload(
        order["id"],
        {
            "ttn_number": result["ttn_number"],
            "np_document_ref": result.get("ref") or "",
            "np_recipient_ref": recipient_ref,
            "np_contact_recipient_ref": contact_ref,
            "np_cost_on_site": result.get("cost_on_site"),
            "np_estimated_delivery_date": result.get("estimated_delivery_date"),
            "np_error": "",
        },
    )
    return storage.get_order(order["id"]) or order


def order_cod_profit(order: dict[str, Any]) -> float:
    if str(order.get("payment_method") or "") != "cod":
        return 0.0
    cod = float(order.get("cod_amount") or 0)
    prepay = float(order.get("prepay") or 0)
    total = float(order.get("total") or 0)
    return round(cod - prepay - total, 2)


def credit_cod_profit_if_needed(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any] | None:
    payload = order.get("payload") or {}
    if payload.get("profit_credited"):
        return None
    profit = order_cod_profit(order)
    if profit <= 0:
        return None
    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        return None
    entry = storage.add_ledger_entry(
        dropper_id=dropper_id,
        amount=profit,
        entry_type="cod_profit_credit",
        title=f"Прибуток з наложки · {order.get('order_number')}",
        note=(
            f"Накладний {round(float(order.get('cod_amount') or 0), 2)} ₴ − "
            f"передплата {round(float(order.get('prepay') or 0), 2)} ₴ − "
            f"«Разом» {round(float(order.get('total') or 0), 2)} ₴"
        ),
        related_order_id=str(order.get("order_number") or ""),
    )
    if entry:
        storage.merge_order_payload(
            order["id"],
            {"profit_credited": True, "profit_amount": profit},
        )
    return entry


async def track_order_statuses_async(
    storage: AppStorage, notify: NotifyFn | None = None
) -> dict[str, int]:
    """Асинхронна обгортка: notify може бути async."""
    client = resolve_np_client(storage)
    stats = {"checked": 0, "updated": 0, "received": 0, "errors": 0}
    if not client:
        return stats

    orders = storage.list_orders_for_tracking(limit=80)
    if not orders:
        return stats

    docs = []
    by_number: dict[str, dict[str, Any]] = {}
    for order in orders:
        number = str(order.get("ttn_number") or "").strip()
        if not number:
            continue
        payload = order.get("payload") or {}
        recipient = payload.get("recipient") or {}
        phone = _digits_phone(recipient.get("phone") or "")
        docs.append({"DocumentNumber": number, "Phone": phone})
        by_number[number] = order

    try:
        rows = client.get_status_documents(docs)
    except Exception:
        logger.exception("NP tracking batch failed")
        stats["errors"] += 1
        return stats

    for row in rows:
        number = str(row.get("Number") or row.get("DocumentNumber") or "").strip()
        order = by_number.get(number)
        if not order:
            continue
        stats["checked"] += 1
        status_code = row.get("StatusCode")
        mapped = map_np_status_code(status_code)
        status_text = str(row.get("Status") or "").strip()
        prev = str(order.get("ttn_status") or "")
        if mapped != prev or status_text:
            storage.update_order_flags(order["id"], ttn_status=mapped)
            storage.merge_order_payload(
                order["id"],
                {
                    "np_status_code": str(status_code or ""),
                    "np_status_text": status_text,
                    "np_tracked_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            stats["updated"] += 1
            order = storage.get_order(order["id"]) or order

        if mapped == "received" and prev != "received":
            entry = credit_cod_profit_if_needed(storage, order)
            if entry:
                stats["received"] += 1
                dropper = storage.get_dropper_by_id(int(order["dropper_id"]))
                if notify and dropper:
                    amount = round(float(entry.get("amount") or 0), 2)
                    try:
                        msg = (
                            f"💰 Посилку отримано · {order.get('order_number')}\n"
                            f"ТТН: {order.get('ttn_number')}\n"
                            f"Прибуток нараховано на баланс: +{amount} ₴"
                        )
                        result = notify(dropper.chat_id, msg)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        logger.exception("notify profit credit failed")
    return stats


async def fulfill_new_order(
    storage: AppStorage,
    order: dict[str, Any],
    notify: NotifyFn | None = None,
) -> dict[str, Any]:
    """Створити ТТН після accept (якщо потрібно) і повідомити дроппера."""
    if order.get("own_ttn"):
        return order
    if str(order.get("ttn_status") or "") not in {"pending_create", "create_error", "none"}:
        return order
    try:
        order = create_ttn_for_order(storage, order)
        if notify and order.get("ttn_number"):
            await notify(
                str(order.get("chat_id") or ""),
                (
                    f"✅ ТТН створено для {order.get('order_number')}\n"
                    f"Номер: {order.get('ttn_number')}\n"
                    f"Статус відстежуватиметься автоматично."
                ),
            )
    except Exception as exc:
        logger.exception("Не вдалося створити ТТН для %s", order.get("order_number"))
        storage.update_order_flags(order["id"], ttn_status="create_error")
        storage.merge_order_payload(order["id"], {"np_error": str(exc)[:500]})
        if notify:
            try:
                await notify(
                    str(order.get("chat_id") or ""),
                    (
                        f"⚠️ Замовлення {order.get('order_number')} прийнято, "
                        f"але ТТН поки не створено: {exc}"
                    ),
                )
            except Exception:
                logger.exception("notify after TTN error failed")
        order = storage.get_order(order["id"]) or order
    return order


async def run_np_maintenance_once(
    storage: AppStorage, notify: NotifyFn | None = None
) -> dict[str, int]:
    """Ретрай створення ТТН + трекінг статусів."""
    stats = {"create_ok": 0, "create_fail": 0}
    pending = storage.list_orders_pending_ttn_create(limit=30)
    for order in pending:
        try:
            updated = create_ttn_for_order(storage, order)
            if updated.get("ttn_number"):
                stats["create_ok"] += 1
                if notify:
                    await notify(
                        str(updated.get("chat_id") or ""),
                        (
                            f"✅ ТТН створено для {updated.get('order_number')}\n"
                            f"Номер: {updated.get('ttn_number')}"
                        ),
                    )
        except Exception:
            stats["create_fail"] += 1
            logger.exception("Retry TTN create failed for %s", order.get("order_number"))

    track = await track_order_statuses_async(storage, notify=notify)
    stats.update(track)
    return stats
