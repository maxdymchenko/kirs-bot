"""Заказы маркетплейсов (Rozetka / Kasta / Prom) → лист «Заказы».

Вызывается Chrome-расширением через /api/ext/* на Render.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from bot.accounts import AppStorage
from bot.orders_sheets import (
    append_order_rows,
    find_sheet_rows_by_order_number,
    replace_order_rows,
    _fmt_money,
    _open_orders_worksheet,
)

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
TIMEOUT = 20

SOURCES = [
    {"id": "rozetka", "label": "Rozetka", "kind": "rozetka", "env": "ROZETKA_API_TOKEN"},
    {"id": "kasta", "label": "Kasta", "kind": "kasta", "env": "KASTA_API_TOKEN"},
    {"id": "prom_kirs", "label": "Пром (Кірс)", "kind": "prom", "env": "PROM_KIRS_TOKEN"},
    {
        "id": "prom_sumka",
        "label": "Пром (Сумка Маркет)",
        "kind": "prom",
        "env": "PROM_SUMKA_TOKEN",
    },
    {"id": "prom_bravo", "label": "Пром (Браво)", "kind": "prom", "env": "PROM_BRAVO_TOKEN"},
    {
        "id": "prom_pro100",
        "label": "Пром (Про100)",
        "kind": "prom",
        "env": "PROM_PRO100_TOKEN",
    },
]


def _trim(value: Any) -> str:
    return str(value or "").strip()


def _pick(*values: Any) -> str:
    for value in values:
        text = _trim(value)
        if text:
            return text
    return ""


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _token(source: dict[str, str]) -> str:
    return _trim(os.getenv(source["env"]))


def enabled_sources() -> list[dict[str, str]]:
    return [s for s in SOURCES if _token(s)]


def _fmt_date(raw: Any) -> str:
    text = _trim(raw)
    now = datetime.now(KYIV)
    if not text:
        return now.strftime("%d.%m.%Y")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KYIV)
        return dt.astimezone(KYIV).strftime("%d.%m.%Y")
    except ValueError:
        return text[:10]


def _payment_label(raw: Any) -> str:
    t = _trim(raw).lower()
    if not t:
        return ""
    if any(
        x in t
        for x in (
            "налож",
            "cod",
            "післяплат",
            "послеплат",
            "наложен",
            "під час отрим",
            "при отриман",
            "оплата при получ",
        )
    ):
        return "НАЛОЖКА"
    if any(x in t for x in ("карт", "card", "online", "оплач")):
        return "КАРТА"
    return _trim(raw).upper()


def _carrier_label(*raws: Any) -> str:
    t = " ".join(_trim(x).lower() for x in raws if _trim(x))
    if not t:
        return ""
    if any(
        m in t
        for m in (
            "rozetka",
            "розетк",
            "rmp",
            "rz-delivery",
            "rz_delivery",
            "w2w",
            "warehouse to warehouse",
        )
    ):
        return "Розетка"
    if any(
        m in t
        for m in (
            "novaposhta",
            "nova_poshta",
            "nova-poshta",
            "nova poshta",
        )
    ) or ("нов" in t and ("почт" in t or "пошт" in t)) or t in {
        "np",
        "нп",
    } or t.startswith("np ") or t.startswith("нп "):
        return "НП"
    if "meest" in t or "микст" in t:
        return "Meest"
    if "укрпошт" in t or "ukrposhta" in t:
        return "Укрпошта"
    return ""


def _person_name(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    return " ".join(
        _trim(obj.get(k))
        for k in ("last_name", "first_name", "middle_name", "patronymic", "second_name")
        if _trim(obj.get(k))
    )


def _client_line(*, city: str, place: str, name: str, phone: str) -> str:
    return " ".join(p for p in (city, place, name, phone) if p)


def _get_json(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    res = requests.get(url, headers=headers, timeout=TIMEOUT)
    try:
        data = res.json()
    except ValueError:
        data = {"message": (res.text or "")[:300]}
    return res.status_code, data


def _map_prom(order: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
    delivery = order.get("delivery_option") or order.get("delivery") or {}
    delivery_data = order.get("delivery_provider_data") or {}
    payment = order.get("payment_option") or order.get("payment_data") or {}
    addr = order.get("delivery_address")
    addr_obj = addr if isinstance(addr, dict) else {}
    addr_text = (
        addr
        if isinstance(addr, str)
        else _pick(addr_obj.get("full_address"), addr_obj.get("address"), delivery_data.get("recipient_address"))
    )
    name = _pick(
        _person_name(
            {
                "last_name": order.get("client_last_name"),
                "first_name": order.get("client_first_name"),
                "middle_name": order.get("client_second_name") or order.get("client_patronymic"),
            }
        ),
        _person_name(order.get("client") if isinstance(order.get("client"), dict) else {}),
        delivery_data.get("recipient_name"),
    )
    items = []
    for p in _as_list(order.get("products")):
        if not isinstance(p, dict):
            continue
        items.append(
            {
                "name": _pick(p.get("name"), p.get("product_name")),
                "code": _pick(p.get("sku"), p.get("external_id"), p.get("article"), p.get("id")),
                "color": _pick(p.get("color"), p.get("model"), p.get("variant")),
                "qty": max(1, int(p.get("quantity") or 1)),
                "retail": p.get("price"),
            }
        )
    return {
        "source_id": source["id"],
        "source_label": source["label"],
        "order_id": str(order.get("id") or ""),
        "date": _fmt_date(order.get("date_created") or order.get("date")),
        "payment": _payment_label(_pick(payment.get("name"), payment.get("type"), order.get("payment_type"))),
        "carrier": _carrier_label(
            delivery_data.get("type"),
            delivery_data.get("provider"),
            delivery.get("name") if isinstance(delivery, dict) else "",
            delivery.get("shipping_service") if isinstance(delivery, dict) else "",
        )
        or "НП",
        "client": _client_line(
            city=_pick(addr_obj.get("city"), delivery_data.get("city_name")),
            place=_pick(addr_obj.get("warehouse"), delivery_data.get("warehouse"), addr_text),
            name=name,
            phone=_pick(order.get("phone"), order.get("client_phone")),
        ),
        "ttn": _pick(delivery_data.get("declaration_number"), order.get("declaration_id"), order.get("ttn")),
        "status": _pick(order.get("status_name"), order.get("status")),
        "order_sum": order.get("full_price") or order.get("price") or order.get("price_with_special_offer"),
        "items": items,
    }


def _fetch_prom(source: dict[str, str], token: str, order_id: str) -> dict[str, Any] | None:
    oid = str(order_id).lstrip("#")
    status, data = _get_json(
        f"https://my.prom.ua/api/v1/orders/{oid}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if status == 404:
        return None
    if status < 200 or status >= 300:
        raise RuntimeError(f"{source['label']}: {data.get('error') or data.get('message') or f'HTTP {status}'}")
    order = data.get("order") if isinstance(data, dict) else None
    if not isinstance(order, dict):
        order = data if isinstance(data, dict) else None
    if not order or not order.get("id"):
        return None
    return _map_prom(order, source)


def _map_rozetka(content: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
    user = content.get("user") if isinstance(content.get("user"), dict) else {}
    delivery = content.get("delivery") if isinstance(content.get("delivery"), dict) else {}
    service = content.get("delivery_service") if isinstance(content.get("delivery_service"), dict) else {}
    items = []
    for p in _as_list(content.get("purchases")):
        if not isinstance(p, dict):
            continue
        item = p.get("item") if isinstance(p.get("item"), dict) else {}
        details = item.get("details")
        items.append(
            {
                "name": _pick(p.get("item_name"), item.get("name"), item.get("name_ua")),
                "code": _pick(item.get("article"), p.get("article"), item.get("id"), p.get("item_id")),
                "color": _pick(p.get("color"), details if isinstance(details, str) else ""),
                "qty": max(1, int(p.get("quantity") or 1)),
                "retail": p.get("price") or p.get("price_with_discount") or p.get("cost"),
            }
        )
    place = " ".join(
        _trim(delivery.get(k))
        for k in ("place_street", "place_house", "place_flat")
        if _trim(delivery.get(k))
    )
    name = _pick(
        delivery.get("recipient_title"),
        content.get("recipient_title"),
        _person_name(
            {
                "last_name": delivery.get("recipient_last_name"),
                "first_name": delivery.get("recipient_first_name"),
                "middle_name": delivery.get("recipient_second_name"),
            }
        ),
        _person_name(user),
    )
    return {
        "source_id": source["id"],
        "source_label": source["label"],
        "order_id": str(content.get("id") or ""),
        "date": _fmt_date(content.get("created")),
        "payment": _payment_label(
            _pick(content.get("payment_type_name"), content.get("payment_type"))
        ),
        "carrier": _carrier_label(
            service.get("name"),
            service.get("type"),
            delivery.get("delivery_service_name"),
            content.get("ttn"),
        )
        or "НП",
        "client": _client_line(
            city=_pick(delivery.get("city"), delivery.get("city_title")),
            place=_pick(place, delivery.get("place_number"), delivery.get("delivery_service_name")),
            name=name,
            phone=_pick(
                delivery.get("recipient_phone"),
                content.get("recipient_phone"),
                content.get("user_phone"),
            ),
        ),
        "ttn": _pick(content.get("ttn"), delivery.get("ttn")),
        "status": _pick(content.get("status_text"), str(content.get("status") or "")),
        "order_sum": content.get("cost_with_discount")
        or content.get("cost")
        or content.get("amount_with_discount")
        or content.get("amount"),
        "items": items,
    }


def _fetch_rozetka(source: dict[str, str], token: str, order_id: str) -> dict[str, Any] | None:
    oid = str(order_id).lstrip("#")
    expand = "user,delivery,purchases,delivery_service,payment_type_name"
    status, data = _get_json(
        f"https://api-seller.rozetka.com.ua/orders/{oid}?expand={expand}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if status in {401, 403}:
        raise RuntimeError("Rozetka: токен не принят")
    if status == 404:
        return None
    if status < 200 or status >= 300:
        err = data.get("errors") if isinstance(data, dict) else None
        msg = ""
        if isinstance(err, dict):
            msg = str(err.get("message") or "")
        raise RuntimeError(f"Rozetka: {msg or data.get('message') or f'HTTP {status}'}")
    content = data.get("content") if isinstance(data, dict) else None
    if not isinstance(content, dict) or not content.get("id"):
        return None
    return _map_rozetka(content, source)


def _map_kasta(order: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
    client = order.get("client") if isinstance(order.get("client"), dict) else {}
    addr = order.get("shipping_address") if isinstance(order.get("shipping_address"), dict) else {}
    delivery = order.get("delivery_properties") if isinstance(order.get("delivery_properties"), dict) else {}
    city_obj = addr.get("city") if isinstance(addr.get("city"), dict) else {}
    wh = addr.get("warehouse") if isinstance(addr.get("warehouse"), dict) else {}
    items_src = _as_list(order.get("ordered_items")) or _as_list(order.get("items"))
    items = []
    for p in items_src:
        if not isinstance(p, dict):
            continue
        barcode = p.get("barcode")
        code = _pick(
            p.get("supplier_code"),
            barcode[0] if isinstance(barcode, list) and barcode else "",
            p.get("unique_sku_id"),
        )
        items.append(
            {
                "name": _pick(p.get("kind"), p.get("name"), p.get("title")),
                "code": code,
                "color": _pick(p.get("color"), p.get("kasta_color"), p.get("size")),
                "qty": max(1, int(p.get("quantity") or p.get("original_quantity") or 1)),
                "retail": p.get("paid_price") or p.get("new_price"),
            }
        )
    statuses = _as_list(order.get("statuses"))
    last_st = statuses[-1] if statuses and isinstance(statuses[-1], dict) else {}
    first_st = statuses[0] if statuses and isinstance(statuses[0], dict) else {}
    return {
        "source_id": source["id"],
        "source_label": source["label"],
        "order_id": str(order.get("id") or ""),
        "date": _fmt_date(order.get("created_at") or first_st.get("created_at")),
        "payment": _payment_label(
            _pick(order.get("requested_payment_method"), order.get("card_payment_state"))
        ),
        "carrier": _carrier_label(delivery.get("type"), order.get("courier_type")) or "НП",
        "client": _client_line(
            city=_pick(city_obj.get("name")),
            place=_pick(wh.get("name"), addr.get("street")),
            name=_pick(_person_name(addr), _person_name(client)),
            phone=_pick(addr.get("phone"), client.get("phone")),
        ),
        "ttn": _pick(delivery.get("declaration_number"), order.get("declaration_number")),
        "status": _pick(order.get("status"), last_st.get("type")),
        "order_sum": last_st.get("amount")
        or first_st.get("amount")
        or sum(
            float(str(it.get("retail") or 0).replace(",", ".") or 0)
            * int(it.get("qty") or 1)
            for it in items
        ),
        "items": items,
    }


def _fetch_kasta(source: dict[str, str], token: str, order_id: str) -> dict[str, Any] | None:
    oid = str(order_id).lstrip("#")
    url = f"https://hub.kasta.ua/api/orders/list?order_id={oid}"
    status, data = _get_json(url, {"Authorization": token, "Accept": "application/json"})
    if status in {401, 403}:
        status, data = _get_json(
            url, {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
    if status in {401, 403}:
        raise RuntimeError("Kasta: токен не принят")
    if status < 200 or status >= 300:
        raise RuntimeError(f"Kasta: {data.get('message') or data.get('error') or f'HTTP {status}'}")
    items = _as_list(data.get("items") if isinstance(data, dict) else data)
    order = next(
        (x for x in items if isinstance(x, dict) and str(x.get("id") or "").lower() == oid.lower()),
        items[0] if items and isinstance(items[0], dict) else None,
    )
    if not order or not order.get("id"):
        return None
    return _map_kasta(order, source)


def _fetch_from_source(source: dict[str, str], order_id: str) -> dict[str, Any] | None:
    token = _token(source)
    if not token:
        return None
    kind = source["kind"]
    if kind == "prom":
        return _fetch_prom(source, token, order_id)
    if kind == "rozetka":
        return _fetch_rozetka(source, token, order_id)
    if kind == "kasta":
        return _fetch_kasta(source, token, order_id)
    return None


def find_marketplace_order(order_id: str, source_id: str = "auto") -> dict[str, Any]:
    oid = _trim(order_id)
    if not oid:
        raise ValueError("Введите номер заказа")
    sources = enabled_sources()
    if not sources:
        raise RuntimeError("Не заданы API-токены маркетплейсов на Render")
    if source_id and source_id != "auto":
        sources = [s for s in sources if s["id"] == source_id]
        if not sources:
            raise RuntimeError("Источник не настроен или нет токена")
    else:
        has_letters = any(c.isalpha() for c in oid) and not oid.isdigit()
        kasta = [s for s in sources if s["kind"] == "kasta"]
        rest = [s for s in sources if s["kind"] != "kasta"]
        sources = [*kasta, *rest] if has_letters else [*rest, *kasta]

    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(sources) or 1) as pool:
        futs = {pool.submit(_fetch_from_source, src, oid): src for src in sources}
        for fut in as_completed(futs):
            src = futs[fut]
            try:
                mapped = fut.result()
            except Exception as exc:
                errors.append(f"{src['label']}: {exc}")
                continue
            if mapped:
                return mapped
    if errors:
        raise RuntimeError(f"Заказ {oid} не найден.\n" + "\n".join(errors))
    raise RuntimeError(f"Заказ {oid} не найден ни на одном магазине")


def _real_location(raw: Any) -> str:
    """Колонка J таблицы наличия: пусто и заглушка «Уточнение» не копируем."""
    text = _trim(raw)
    if not text:
        return ""
    folded = text.casefold()
    if folded in {"-", "—", "–", "н/д", "нет", "немає"}:
        return ""
    if folded.startswith("уточнен"):
        return ""
    return text


def _lookup_location(catalog: Any, code: str, color: str) -> str:
    """Расположение из столбца J по коду товара. Нет значения в J — пустая ячейка."""
    if catalog is None or not _trim(code):
        return ""
    from bot.orders_sheets import _lookup_variant_meta

    _retail, location = _lookup_variant_meta(catalog, code, color)
    return _real_location(location)


def build_sheet_rows(
    mapped: dict[str, Any],
    comment: str = "",
    *,
    catalog: Any = None,
) -> list[list[Any]]:
    items = mapped.get("items") or []
    if not items:
        items = [{"name": "", "code": "", "color": "", "qty": 1, "retail": ""}]
    note = _trim(comment)
    sale = _fmt_money(mapped.get("order_sum"))
    rows = []
    for item in items:
        code = _trim(item.get("code"))
        color = _trim(item.get("color"))
        location = _lookup_location(catalog, code, color)
        rows.append(
            [
                mapped.get("date") or "",
                mapped.get("order_id") or "",
                mapped.get("payment") or "",
                mapped.get("carrier") or "",
                _trim(item.get("name")),
                code,
                color,
                item.get("qty") or 1,
                sale,
                "",
                mapped.get("source_label") or "",
                mapped.get("client") or "",
                mapped.get("ttn") or "",
                mapped.get("status") or "",
                note,
                "",
                "",
                location,
            ]
        )
    return rows


def preview_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "date": r[0],
                "orderId": r[1],
                "payment": r[2],
                "carrier": r[3],
                "name": r[4],
                "code": r[5],
                "color": r[6],
                "qty": r[7],
                "retail": r[8],
                "source": r[10],
                "client": r[11],
                "ttn": r[12],
                "status": r[13],
                "note": r[14],
            }
        )
    return out


def write_marketplace_order(
    storage: AppStorage,
    *,
    order_id: str,
    source_id: str = "auto",
    comment: str = "",
    catalog: Any = None,
) -> dict[str, Any]:
    mapped = find_marketplace_order(order_id, source_id)
    rows = build_sheet_rows(mapped, comment, catalog=catalog)
    ws = _open_orders_worksheet(storage)
    existing = find_sheet_rows_by_order_number(ws, mapped["order_id"])
    if existing:
        written = replace_order_rows(ws, existing, rows)
        return {
            "ok": True,
            "already": True,
            "updated": True,
            "source": {"id": mapped["source_id"], "label": mapped["source_label"]},
            "orderId": mapped["order_id"],
            "preview": preview_rows(rows),
            "rows": written,
            "message": (
                f"Перезаписано заказ {mapped['order_id']} "
                f"в строках {', '.join(str(x) for x in written)}"
            ),
        }
    written = append_order_rows(ws, rows)
    return {
        "ok": True,
        "already": False,
        "updated": False,
        "source": {"id": mapped["source_id"], "label": mapped["source_label"]},
        "orderId": mapped["order_id"],
        "preview": preview_rows(rows),
        "rows": written,
        "message": f"Записано {len(rows)} стр. заказа {mapped['order_id']}",
    }
