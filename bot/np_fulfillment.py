"""Створення ТТН Нової Пошти та трекінг до «отримано» + нарахування прибутку."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Callable, TypeVar

from bot.accounts import AppStorage
from bot.novaposhta import (
    NovaPoshtaClient,
    NovaPoshtaError,
    extract_delivery_cost,
    extract_warehouse_arrival_iso,
    map_np_status_code,
)

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, str], Any]
OwnerNotifyFn = Callable[[str], Any]
T = TypeVar("T")

TERMINAL_TTN_STATUSES = frozenset(
    {
        "received",
        "returned",
        "refused",
        "failed",
        "provided",
        "cancelled",
        "return_at_warehouse",
    }
)


def _digits_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("0") and len(digits) == 10:
        digits = "38" + digits
    if digits.startswith("380") and len(digits) >= 12:
        return digits[:12]
    return digits


def list_np_clients(
    storage: AppStorage,
) -> list[tuple[str, NovaPoshtaClient, bool]]:
    """
    Порядок: ключі з галочкою (основні) → без галочки (резерв) → NOVA_POSHTA_API_KEY.
    Третій елемент: True = основний (галочка), False = резерв.
    """
    out: list[tuple[str, NovaPoshtaClient, bool]] = []
    seen: set[str] = set()
    for row in storage.get_np_api_keys_for_rotation():
        key = str(row.get("api_key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        is_primary = bool(row.get("enabled"))
        base = str(row.get("label") or "НП").strip() or "НП"
        label = base if is_primary else f"{base} (резерв)"
        out.append((label, NovaPoshtaClient(key), is_primary))
    env_key = (os.getenv("NOVA_POSHTA_API_KEY") or "").strip()
    if env_key and env_key not in seen:
        client = NovaPoshtaClient(env_key)
        if client.configured():
            out.append(("env (резерв)", client, False))
    elif not out:
        client = NovaPoshtaClient()
        if client.configured():
            out.append(("env (резерв)", client, False))
    return out


def resolve_np_client(storage: AppStorage) -> NovaPoshtaClient | None:
    clients = list_np_clients(storage)
    return clients[0][1] if clients else None


def call_with_np_key_rotation(
    storage: AppStorage,
    operation: str,
    fn: Callable[[NovaPoshtaClient], T],
) -> T:
    """Викликати fn(client); при помилці — наступний ключ (основні, потім резерв)."""
    clients = list_np_clients(storage)
    if not clients:
        raise NovaPoshtaError("Немає API-ключа Нової Пошти")
    errors: list[str] = []
    for label, client, _is_primary in clients:
        try:
            result = fn(client)
            if len(clients) > 1:
                logger.info("NP %s ok via key «%s»", operation, label)
            return result
        except NovaPoshtaError as exc:
            logger.warning("NP %s failed via «%s»: %s", operation, label, exc)
            errors.append(f"{label}: {exc}")
    raise NovaPoshtaError("; ".join(errors) or f"NP {operation} failed")


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

    clients = list_np_clients(storage)
    if not clients:
        storage.update_order_flags(order["id"], ttn_status="create_error")
        storage.merge_order_payload(
            order["id"],
            {"np_error": "Немає API-ключа Нової Пошти"},
        )
        raise NovaPoshtaError("Немає API-ключа Нової Пошти")

    settings = storage.get_general_settings()
    errors: list[str] = []
    last_exc: Exception | None = None
    for label, client, is_primary in clients:
        try:
            sender = _pick_sender_bundle(client, settings)
            recipient_ref, contact_ref = _ensure_recipient_refs(client, order)
            props = _build_save_props(
                order, settings, sender, recipient_ref, contact_ref
            )
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
                    "np_api_key_label": label,
                    "np_used_backup_key": not is_primary,
                    "np_error": "",
                },
            )
            if not is_primary or len(clients) > 1:
                logger.info(
                    "TTN %s created via key «%s» (primary=%s)",
                    result["ttn_number"],
                    label,
                    is_primary,
                )
            return storage.get_order(order["id"]) or order
        except NovaPoshtaError as exc:
            last_exc = exc
            logger.warning(
                "TTN create failed via «%s» for %s: %s",
                label,
                order.get("order_number"),
                exc,
            )
            errors.append(f"{label}: {exc}")
        except Exception as exc:
            last_exc = exc
            logger.exception(
                "TTN create unexpected error via «%s» for %s",
                label,
                order.get("order_number"),
            )
            errors.append(f"{label}: {exc}")

    msg = "; ".join(errors) or str(last_exc or "Не вдалося створити ТТН")
    storage.update_order_flags(order["id"], ttn_status="create_error")
    storage.merge_order_payload(order["id"], {"np_error": msg[:500]})
    raise NovaPoshtaError(msg) from last_exc


AWAITING_SHIPMENT_STATUSES = frozenset(
    {"none", "pending_create", "create_error", "created"}
)
SHIPPED_OR_FINAL_STATUSES = frozenset(
    {
        "in_transit",
        "at_warehouse",
        "received",
        "refused",
        "returned",
        "return_at_warehouse",
        "failed",
    }
)


def can_recreate_ttn(order: dict[str, Any]) -> bool:
    """
    Пересоздати ТТН можна лише поки накладна ще «чекає відправки»
    (не власна ТТН, статус created/pending або NP StatusCode=1).
    """
    if order.get("own_ttn"):
        return False
    status = str(order.get("ttn_status") or "none").strip() or "none"
    if status in SHIPPED_OR_FINAL_STATUSES:
        return False
    if status in AWAITING_SHIPMENT_STATUSES:
        return True
    code = str((order.get("payload") or {}).get("np_status_code") or "").strip()
    return code == "1"


def recreate_ttn_for_order(
    storage: AppStorage, order: dict[str, Any]
) -> dict[str, Any]:
    """
    Видалити стару ТТН в кабінеті НП (якщо є Ref) і створити нову.
    Викликати лише коли can_recreate_ttn(order) == True.
    """
    if order.get("own_ttn"):
        return order
    if not can_recreate_ttn(order):
        return order

    payload = dict(order.get("payload") or {})
    doc_ref = str(payload.get("np_document_ref") or "").strip()
    old_ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()

    delete_error = ""
    if doc_ref:
        clients = list_np_clients(storage)
        deleted = False
        for label, client, _is_primary in clients:
            try:
                client.delete_internet_document(doc_ref)
                deleted = True
                logger.info(
                    "Deleted TTN ref %s via «%s» for order %s",
                    doc_ref,
                    label,
                    order.get("order_number"),
                )
                break
            except NovaPoshtaError as exc:
                delete_error = str(exc)
                logger.warning(
                    "TTN delete failed via «%s» for %s: %s",
                    label,
                    order.get("order_number"),
                    exc,
                )
            except Exception as exc:
                delete_error = str(exc)
                logger.exception(
                    "TTN delete unexpected via «%s» for %s",
                    label,
                    order.get("order_number"),
                )
        if not deleted and old_ttn:
            # Без успішного delete не створюємо другу накладну «всліпу»
            storage.update_order_flags(order["id"], ttn_status="create_error")
            storage.merge_order_payload(
                order["id"],
                {
                    "np_error": (
                        f"Не вдалося видалити стару ТТН {old_ttn}: "
                        f"{delete_error or 'помилка НП'}"
                    )[:500],
                },
            )
            raise NovaPoshtaError(
                f"Не вдалося видалити стару ТТН {old_ttn}: {delete_error or 'помилка НП'}"
            )
    elif old_ttn:
        logger.warning(
            "Recreating TTN for %s without np_document_ref (old=%s)",
            order.get("order_number"),
            old_ttn,
        )

    # Скидаємо номер — create_ttn_for_order вимагає порожній ttn_number
    storage.update_order_flags(
        order["id"],
        ttn_number="",
        ttn_status="pending_create",
    )
    storage.merge_order_payload(
        order["id"],
        {
            "ttn_number": "",
            "np_document_ref": "",
            "np_error": "",
            "np_status_code": "",
            "np_status_text": "",
            "np_tracked_at": "",
            "np_cost_on_site": None,
            "np_estimated_delivery_date": "",
            "np_api_key_label": "",
            "np_used_backup_key": False,
            "np_backup_owner_notified": False,
            "old_ttn_before_recreate": old_ttn,
        },
    )
    order = storage.get_order(order["id"]) or order
    return create_ttn_for_order(storage, order)


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
    if payload.get("return_delivery_debited"):
        # Відмова/повернення — прибутку немає
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
            f"«Дроп ціна» {round(float(order.get('total') or 0), 2)} ₴"
        ),
        related_order_id=str(order.get("order_number") or ""),
    )
    if entry:
        storage.merge_order_payload(
            order["id"],
            {"profit_credited": True, "profit_amount": profit},
        )
    return entry


def debit_return_delivery_if_needed(
    storage: AppStorage,
    order: dict[str, Any],
    delivery_cost: float,
) -> dict[str, Any] | None:
    """
    Відмова/повернення: списати вартість доставки з балансу дроппера (збиток).
    Прибуток не нараховуємо.
    """
    payload = order.get("payload") or {}
    if payload.get("return_delivery_debited"):
        return None
    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        return None
    cost = round(max(0.0, float(delivery_cost or 0)), 2)
    # Навіть якщо вартість 0 — ставимо прапорець, щоб не крутити повторно
    if cost <= 0:
        storage.merge_order_payload(
            order["id"],
            {
                "return_delivery_debited": True,
                "return_delivery_cost": 0,
                "profit_credited": False,
            },
        )
        return None
    entry = storage.add_ledger_entry(
        dropper_id=dropper_id,
        amount=-cost,
        entry_type="return_delivery_debit",
        title=f"Доставка при відмові/поверненні · {order.get('order_number')}",
        note=(
            f"Посилку не отримано. Вартість доставки {cost} ₴ списано з балансу дроппера."
        ),
        related_order_id=str(order.get("order_number") or ""),
    )
    storage.merge_order_payload(
        order["id"],
        {
            "return_delivery_debited": True,
            "return_delivery_cost": cost,
            "np_delivery_cost": cost,
            "profit_credited": False,
        },
    )
    return entry


def _dropper_allows_profit_notify(storage: AppStorage, order: dict[str, Any]) -> bool:
    """Опційне сповіщення: посилку отримано / прибуток на баланс."""
    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        return False
    dropper = storage.get_dropper_by_id(dropper_id)
    return bool(dropper and getattr(dropper, "notify_shipping_events", False))


def _order_is_cod(order: dict[str, Any]) -> bool:
    return str(order.get("payment_method") or "") == "cod"


async def _maybe_eval_buyout(
    storage: AppStorage,
    order: dict[str, Any],
    notify: NotifyFn | None,
) -> None:
    dropper_id = int(order.get("dropper_id") or 0)
    if not dropper_id:
        return
    dropper = storage.get_dropper_by_id(dropper_id)
    if not dropper:
        return
    try:
        from bot.buyout import evaluate_dropper_buyout

        await evaluate_dropper_buyout(storage, dropper, notify=notify)
    except Exception:
        logger.exception("buyout eval after status failed dropper_id=%s", dropper_id)


async def _send_dropper_chat(
    notify: NotifyFn | None,
    chat_id: str,
    text: str,
) -> None:
    if not notify or not text or not chat_id:
        return
    result = notify(chat_id, text)
    if hasattr(result, "__await__"):
        await result


async def _notify_ttn_created_cod(
    order: dict[str, Any],
    notify: NotifyFn | None,
    text: str,
) -> None:
    """ТТН створено — завжди пишемо дропперу для замовлень з наложки."""
    if not _order_is_cod(order):
        return
    await _send_dropper_chat(notify, str(order.get("chat_id") or ""), text)


async def _maybe_profit_notify(
    storage: AppStorage,
    order: dict[str, Any],
    notify: NotifyFn | None,
    text: str,
) -> None:
    """Отримання / нарахування / повернення — лише якщо дроппер увімкнув у налаштуваннях."""
    if not _dropper_allows_profit_notify(storage, order):
        return
    await _send_dropper_chat(notify, str(order.get("chat_id") or ""), text)


async def _notify_owner_backup_ttn(
    storage: AppStorage,
    order: dict[str, Any],
    owner_notify: OwnerNotifyFn | None,
) -> None:
    """Повідомити власника, якщо ТТН створено з резервного кабінету (без галочки)."""
    if not owner_notify:
        return
    payload = order.get("payload") or {}
    if not payload.get("np_used_backup_key"):
        return
    if payload.get("np_backup_owner_notified"):
        return
    label = str(payload.get("np_api_key_label") or "резерв").strip()
    text = (
        f"⚠️ ТТН створено з резервного кабінету НП\n"
        f"Замовлення: {order.get('order_number')}\n"
        f"ТТН: {order.get('ttn_number')}\n"
        f"Кабінет: {label}\n"
        f"Основний ключ (з галочкою) не спрацював — перевірте кабінет НП."
    )
    try:
        result = owner_notify(text)
        if hasattr(result, "__await__"):
            await result
        storage.merge_order_payload(
            order["id"], {"np_backup_owner_notified": True}
        )
    except Exception:
        logger.exception(
            "Не вдалося повідомити власника про резервну ТТН %s",
            order.get("order_number"),
        )


async def apply_tracking_event(
    storage: AppStorage,
    order: dict[str, Any],
    *,
    status_code: str | int | None = None,
    status_text: str = "",
    tracking_row: dict[str, Any] | None = None,
    notify: NotifyFn | None = None,
) -> dict[str, Any]:
    """
    Застосувати статус ТТН до замовлення:
    - received → прибуток з наложки
    - returned → списання вартості доставки (без прибутку)
    """
    result = {
        "updated": False,
        "received": False,
        "returned": False,
        "mapped": "",
        "order": order,
    }
    if not order or order.get("own_ttn"):
        return result

    mapped = map_np_status_code(status_code, status_text)
    prev = str(order.get("ttn_status") or "")
    payload_prev = order.get("payload") or {}
    ever_received = bool(
        payload_prev.get("ever_received")
        or prev == "received"
        or payload_prev.get("profit_credited")
    )
    # Після отримання клієнтом подальший «return» показуємо як повернення дроппера
    if mapped in {"refused", "returned"} and ever_received:
        mapped = "returned"
    result["mapped"] = mapped

    patch = {
        "np_status_code": str(status_code or ""),
        "np_status_text": str(status_text or "").strip(),
        "np_tracked_at": datetime.now().isoformat(timespec="seconds"),
    }
    delivery_cost = extract_delivery_cost(tracking_row, order)
    if delivery_cost > 0:
        patch["np_delivery_cost"] = delivery_cost

    if mapped == "at_warehouse" and not payload_prev.get("np_at_warehouse_at"):
        arrived = extract_warehouse_arrival_iso(tracking_row) or datetime.now().isoformat(
            timespec="seconds"
        )
        patch["np_at_warehouse_at"] = arrived

    if mapped == "received":
        patch["ever_received"] = True

    if mapped == "returned" and ever_received:
        patch["return_after_received"] = True

    # Історія руху посилки (без дублів підряд з тим самим status_code)
    events = list(payload_prev.get("tracking_events") or [])
    if not isinstance(events, list):
        events = []
    code_s = str(status_code or "").strip()
    text_s = str(status_text or "").strip()
    last = events[-1] if events else None
    last_code = str((last or {}).get("status_code") or "") if isinstance(last, dict) else ""
    last_mapped = str((last or {}).get("ttn_status") or "") if isinstance(last, dict) else ""
    if code_s or text_s or mapped:
        if last_code != code_s or last_mapped != mapped:
            events.append(
                {
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "status_code": code_s,
                    "status_text": text_s,
                    "ttn_status": mapped,
                }
            )
            # тримаємо розумний ліміт
            patch["tracking_events"] = events[-80:]

    if mapped != prev or status_text or delivery_cost > 0 or len(patch) > 3:
        storage.update_order_flags(order["id"], ttn_status=mapped)
        storage.merge_order_payload(order["id"], patch)
        result["updated"] = True
        order = storage.get_order(order["id"]) or order
        result["order"] = order
        if mapped != prev:
            try:
                storage.add_order_change(
                    order_id=int(order["id"]),
                    order_number=str(order.get("order_number") or ""),
                    actor_role="system",
                    actor_label="Нова Пошта",
                    change_type="tracking",
                    summary=f"Статус доставки: {prev or '—'} → {mapped}"
                    + (f" ({text_s})" if text_s else ""),
                    diff=[
                        {
                            "field": "ttn_status",
                            "old": prev,
                            "new": mapped,
                        }
                    ],
                )
            except Exception:
                logger.exception("order_change tracking failed")

    if mapped == "received" and prev != "received":
        entry = credit_cod_profit_if_needed(storage, order)
        if entry:
            result["received"] = True
            amount = round(float(entry.get("amount") or 0), 2)
            try:
                await _maybe_profit_notify(
                    storage,
                    order,
                    notify,
                    (
                        f"💰 Посилку отримано · {order.get('order_number')}\n"
                        f"ТТН: {order.get('ttn_number')}\n"
                        f"Прибуток нараховано на баланс: +{amount} ₴"
                    ),
                )
            except Exception:
                logger.exception("notify profit credit failed")
            order = storage.get_order(order["id"]) or order
            result["order"] = order
            await _maybe_eval_buyout(storage, order, notify)

    if mapped in {"returned", "refused"} and prev not in {"returned", "refused"}:
        # Якщо прибуток уже встигли нарахувати — сторнуємо
        payload = order.get("payload") or {}
        if payload.get("profit_credited") and not payload.get("profit_reversed"):
            prev_profit = round(float(payload.get("profit_amount") or 0), 2)
            if prev_profit > 0:
                storage.add_ledger_entry(
                    dropper_id=int(order["dropper_id"]),
                    amount=-prev_profit,
                    entry_type="cod_profit_reversal",
                    title=f"Сторно прибутку (повернення) · {order.get('order_number')}",
                    note="Посилку повернуто/відмовлено після нарахування прибутку",
                    related_order_id=str(order.get("order_number") or ""),
                )
                storage.merge_order_payload(
                    order["id"],
                    {"profit_reversed": True, "profit_credited": False},
                )
                order = storage.get_order(order["id"]) or order

        cost = extract_delivery_cost(tracking_row, order)
        entry = debit_return_delivery_if_needed(storage, order, cost)
        result["returned"] = True
        amount = round(abs(float((entry or {}).get("amount") or cost or 0)), 2)
        label = "Повернення" if mapped == "returned" and ever_received else "Відмова"
        try:
            await _maybe_profit_notify(
                storage,
                order,
                notify,
                (
                    f"↩️ {label} · {order.get('order_number')}\n"
                    f"ТТН: {order.get('ttn_number')}\n"
                    + (
                        f"Вартість доставки списано з балансу: −{amount} ₴"
                        if amount > 0
                        else "Прибуток не нараховано (посилку не отримано)."
                    )
                ),
            )
        except Exception:
            logger.exception("notify return debit failed")
        order = storage.get_order(order["id"]) or order
        result["order"] = order
        await _maybe_eval_buyout(storage, order, notify)

    return result


async def track_order_statuses_async(
    storage: AppStorage, notify: NotifyFn | None = None
) -> dict[str, int]:
    """Опитування статусів ТТН (основний канал; webhook — додатковий, якщо підключений)."""
    clients = list_np_clients(storage)
    stats = {
        "checked": 0,
        "updated": 0,
        "received": 0,
        "returned": 0,
        "errors": 0,
    }
    if not clients:
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

    rows: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for label, client, _is_primary in clients:
        try:
            rows = client.get_status_documents(docs)
            break
        except Exception as exc:
            last_err = exc
            logger.warning("NP tracking batch failed via «%s»: %s", label, exc)
    else:
        logger.error("NP tracking batch failed on all keys: %s", last_err)
        stats["errors"] += 1
        return stats

    for row in rows:
        number = str(row.get("Number") or row.get("DocumentNumber") or "").strip()
        order = by_number.get(number)
        if not order:
            continue
        stats["checked"] += 1
        applied = await apply_tracking_event(
            storage,
            order,
            status_code=row.get("StatusCode"),
            status_text=str(row.get("Status") or ""),
            tracking_row=row,
            notify=notify,
        )
        if applied["updated"]:
            stats["updated"] += 1
        if applied["received"]:
            stats["received"] += 1
        if applied["returned"]:
            stats["returned"] += 1
    return stats


def _webhook_items(payload: Any) -> list[Any]:
    """Розпарсити різні формати push від НП / Integration Platform / посередників."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "Documents", "documents", "items", "TrackingDocuments"):
        val = payload.get(key)
        if isinstance(val, list):
            return val
    nested = payload.get("message") or payload.get("payload") or payload.get("body")
    if isinstance(nested, list):
        return nested
    if isinstance(nested, dict):
        for key in ("data", "Documents", "documents"):
            val = nested.get(key)
            if isinstance(val, list):
                return val
        return [nested]
    return [payload]


def _webhook_ttn_number(item: dict[str, Any]) -> str:
    return str(
        item.get("DocumentNumber")
        or item.get("Number")
        or item.get("IntDocNumber")
        or item.get("docNumber")
        or item.get("documentNumber")
        or item.get("ttn")
        or item.get("TTN")
        or ""
    ).strip()


def _webhook_status_code(item: dict[str, Any]) -> Any:
    return (
        item.get("StatusCode")
        or item.get("status_code")
        or item.get("StatusCodeNew")
        or item.get("StateId")
        or item.get("stateId")
        or item.get("statusCode")
    )


def _webhook_status_text(item: dict[str, Any]) -> str:
    return str(
        item.get("Status")
        or item.get("status")
        or item.get("StatusName")
        or item.get("stateName")
        or item.get("status_text")
        or ""
    ).strip()


async def apply_webhook_payload(
    storage: AppStorage,
    payload: Any,
    notify: NotifyFn | None = None,
) -> dict[str, Any]:
    """
    Webhook від НП / зовнішнього трекінгу — основний канал оновлення статусів ТТН.
    Приймає один об'єкт або список з полями DocumentNumber/Number + StatusCode/Status.
    """
    items = _webhook_items(payload)
    stats = {"processed": 0, "updated": 0, "received": 0, "returned": 0, "skipped": 0}
    for item in items:
        if not isinstance(item, dict):
            stats["skipped"] += 1
            continue
        number = _webhook_ttn_number(item)
        if not number:
            stats["skipped"] += 1
            continue
        order = storage.get_order_by_ttn(number)
        if not order:
            stats["skipped"] += 1
            continue
        stats["processed"] += 1
        applied = await apply_tracking_event(
            storage,
            order,
            status_code=_webhook_status_code(item),
            status_text=_webhook_status_text(item),
            tracking_row=item,
            notify=notify,
        )
        if applied["updated"]:
            stats["updated"] += 1
        if applied["received"]:
            stats["received"] += 1
        if applied["returned"]:
            stats["returned"] += 1
    return stats


async def fulfill_new_order(
    storage: AppStorage,
    order: dict[str, Any],
    notify: NotifyFn | None = None,
    owner_notify: OwnerNotifyFn | None = None,
) -> dict[str, Any]:
    """Створити ТТН після accept (якщо потрібно) і повідомити дроппера."""
    if order.get("own_ttn"):
        return order
    if str(order.get("ttn_status") or "") not in {"pending_create", "create_error", "none"}:
        return order
    try:
        order = create_ttn_for_order(storage, order)
        if order.get("ttn_number"):
            await _notify_owner_backup_ttn(storage, order, owner_notify)
            await _notify_ttn_created_cod(
                order,
                notify,
                (
                    f"✅ ТТН створено для {order.get('order_number')}\n"
                    f"Номер: {order.get('ttn_number')}\n"
                    f"Статус перевірятиметься автоматично (до ~30 хв)."
                ),
            )
    except Exception as exc:
        logger.exception("Не вдалося створити ТТН для %s", order.get("order_number"))
        storage.update_order_flags(order["id"], ttn_status="create_error")
        storage.merge_order_payload(order["id"], {"np_error": str(exc)[:500]})
        try:
            await _notify_ttn_created_cod(
                order,
                notify,
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
    storage: AppStorage,
    notify: NotifyFn | None = None,
    owner_notify: OwnerNotifyFn | None = None,
) -> dict[str, int]:
    """Ретрай створення ТТН + опитування статусів (раз на ~30 хв з main)."""
    stats = {"create_ok": 0, "create_fail": 0, "backup_used": 0}
    pending = storage.list_orders_pending_ttn_create(limit=30)
    for order in pending:
        try:
            updated = create_ttn_for_order(storage, order)
            if updated.get("ttn_number"):
                stats["create_ok"] += 1
                if (updated.get("payload") or {}).get("np_used_backup_key"):
                    stats["backup_used"] += 1
                await _notify_owner_backup_ttn(storage, updated, owner_notify)
                await _notify_ttn_created_cod(
                    updated,
                    notify,
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
