"""Заказы маркетплейсов (Rozetka / Kasta / Prom) → лист «Заказы».

Вызывается Chrome-расширением через /api/ext/* на Render.
"""

from __future__ import annotations

import logging
import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from bot.accounts import AppStorage
from bot.orders_sheets import (
    COL_ORDER_NO,
    append_order_rows,
    find_sheet_rows_by_order_number,
    replace_order_rows,
    _find_catalog_variants,
    _fmt_money,
    _is_generic_sheet_color,
    _lookup_unique_catalog_color,
    _match_catalog_color,
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


def _as_text(value: Any, *keys: str, _depth: int = 0) -> str:
    """Строка для листа: словари не сериализуем, берём человекочитаемое поле."""
    if _depth > 4 or value is None or isinstance(value, bool):
        return ""
    if isinstance(value, dict):
        search = keys or (
            "name_ua",
            "city_name",
            "full_address",
            "address",
            "title",
            "name",
            "number",
            "label",
        )
        for key in search:
            text = _as_text(value.get(key), _depth=_depth + 1)
            if text:
                return text
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _as_text(item, *keys, _depth=_depth + 1)
            if text:
                return text
        return ""
    return str(value).strip()


def _trim(value: Any) -> str:
    return _as_text(value)


def _pick(*values: Any) -> str:
    for value in values:
        text = _as_text(value)
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
    if any(
        x in t
        for x in (
            "карт",
            "card",
            "online",
            "оплач",
            "apple",
            "google pay",
            "gpay",
            "privat",
            "liqpay",
            "portmone",
        )
    ):
        return "КАРТА"
    return _trim(raw).upper()


def _carrier_label(*raws: Any) -> str:
    """Визначити службу доставки. W2W у Prom — це відділення НП, не Розетка."""
    parts = [_trim(x).lower().replace("-", "_") for x in raws if _trim(x)]
    t = " ".join(parts)
    if not t:
        return ""
    tokens = set(re.split(r"[^\w]+", t))

    is_np = (
        "novaposhta" in t
        or "nova_poshta" in t
        or "nova poshta" in t
        or ("нов" in t and ("почт" in t or "пошт" in t))
        or tokens & {"np", "нп"}
        or t.startswith("np ")
        or t.startswith("нп ")
    )
    if is_np:
        return "НП"
    if "укрпошт" in t or "ukrposhta" in t or "ukr_poshta" in t:
        return "Укрпошта"
    if "meest" in t or "микст" in t:
        return "Meest"
    is_rozetka = any(
        m in t
        for m in (
            "rozetka",
            "розетк",
            "rz_delivery",
            "rz delivery",
        )
    ) or "rmp" in tokens
    if is_rozetka:
        return "Розетка"
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


def _looks_like_prom_id(value: Any) -> bool:
    text = _trim(value)
    return bool(text.isdigit() and len(text) >= 8)


def _prom_warehouse_code(p: dict[str, Any], prom_id: str = "") -> str:
    """Складський код (стовпець B), не числовий ID товару Prom."""
    pid = prom_id or _trim(p.get("id"))
    for key in ("external_id", "article", "sku"):
        text = _trim(p.get(key))
        if not text or text == pid or _looks_like_prom_id(text):
            continue
        return text
    return ""


def _prom_order_product(p: dict[str, Any]) -> dict[str, Any]:
    inner = p.get("product")
    if isinstance(inner, dict):
        merged = dict(inner)
        for key, val in p.items():
            if key != "product" and val not in (None, ""):
                merged[key] = val
        return merged
    return p


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
        p = _prom_order_product(p)
        product_name = _pick(p.get("name"), p.get("product_name"))
        prom_id = _pick(p.get("id"), p.get("product_id"))
        items.append(
            {
                "name": product_name,
                "code": _prom_warehouse_code(p, prom_id),
                "product_id": prom_id,
                "color": _pick(p.get("color"), p.get("model"), p.get("variant")),
                "color_candidates": [product_name] if product_name else [],
                "qty": max(1, int(p.get("quantity") or 1)),
                "retail": p.get("price") if p.get("price") not in (None, "") else p.get("total_price"),
            }
        )
    return {
        "source_id": source["id"],
        "source_label": source["label"],
        "order_id": str(order.get("id") or ""),
        "date": _fmt_date(order.get("date_created") or order.get("date")),
        "payment": _payment_label(_pick(payment.get("name"), payment.get("type"), order.get("payment_type"))),
        "carrier": _carrier_label(
            delivery_data.get("provider"),
            delivery_data.get("type"),
            delivery.get("name") if isinstance(delivery, dict) else "",
            delivery.get("shipping_service") if isinstance(delivery, dict) else "",
        )
        or "НП",
        "client": _client_line(
            city=_pick(
                _as_text(addr_obj.get("city"), "name_ua", "city_name", "title", "name"),
                delivery_data.get("city_name"),
            ),
            place=_pick(
                _as_text(addr_obj.get("warehouse"), "name", "number", "title"),
                _as_text(delivery_data.get("warehouse"), "name", "number", "title"),
                addr_text,
            ),
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
    mapped = _map_prom(order, source)
    try:
        _fill_prom_item_meta(mapped, token)
    except Exception:
        logger.exception("prom product enrich failed for %s", mapped.get("order_id"))
    return mapped


_COLOR_ATTR_RE = re.compile(
    r"колір|цвет|colour|color|окрас|відтін|оттен",
    re.IGNORECASE,
)
_COLOR_NAME_KEYS = (
    "option_name",
    "attribute_name",
    "name",
    "name_ua",
    "title",
    "title_ua",
    "attr",
    "attribute",
    "param",
    "parameter",
    "label",
)
_COLOR_VALUE_KEYS = (
    "value",
    "attribute_value",
    "option_value",
    "value_name",
    "text",
    "color",
    "color_name",
    "colour",
)


def _looks_like_color_attr(name: Any) -> bool:
    return bool(_COLOR_ATTR_RE.search(str(name or "")))


def _parse_maybe_json(raw: Any) -> Any:
    if isinstance(raw, str):
        text = raw.strip()
        if text[:1] in "{[":
            try:
                return json.loads(text)
            except ValueError:
                return raw
    return raw


def _usable_color_text(value: Any) -> str:
    text = _trim(value)
    if not text or text.isdigit() or len(text) > 60:
        return ""
    lowered = text.casefold()
    if lowered.startswith("http") or lowered in {"null", "none", "-", "—"}:
        return ""
    return text


def _walk_rozetka_attrs(raw: Any, named: list[str], values: list[str]) -> None:
    raw = _parse_maybe_json(raw)
    if raw is None or isinstance(raw, bool):
        return
    if isinstance(raw, str):
        text = _usable_color_text(raw)
        if text and text not in values:
            values.append(text)
        return
    if isinstance(raw, dict):
        name = ""
        for key in _COLOR_NAME_KEYS:
            if raw.get(key):
                name = raw.get(key)
                break
        for key in _COLOR_VALUE_KEYS:
            val = raw.get(key)
            if val in (None, "", []):
                continue
            if isinstance(val, list):
                for item in val:
                    text = _usable_color_text(item)
                    if text and _looks_like_color_attr(name) and text not in named:
                        named.append(text)
                    if text and text not in values:
                        values.append(text)
            else:
                text = _usable_color_text(val)
                if text and _looks_like_color_attr(name) and text not in named:
                    named.append(text)
                if text and text not in values:
                    values.append(text)
        for key, val in raw.items():
            if key in _COLOR_NAME_KEYS or key in _COLOR_VALUE_KEYS:
                continue
            if _looks_like_color_attr(key):
                text = _usable_color_text(val)
                if text and text not in named:
                    named.append(text)
                if text and text not in values:
                    values.append(text)
                continue
            if isinstance(val, (dict, list)) or (
                isinstance(val, str) and val.strip()[:1] in "{["
            ):
                _walk_rozetka_attrs(val, named, values)
            else:
                text = _usable_color_text(val)
                if text and text not in values:
                    values.append(text)
        return
    if isinstance(raw, list):
        for item in raw:
            _walk_rozetka_attrs(item, named, values)


def _extract_rozetka_color(*sources: Any) -> str:
    """Колір з характеристики «Колір / Цвет / color», якщо API віддала назву поля."""
    named: list[str] = []
    values: list[str] = []
    for src in sources:
        parsed = _parse_maybe_json(src)
        if isinstance(src, str) and not isinstance(parsed, (dict, list)):
            text = _usable_color_text(src)
            if text and text not in named:
                named.append(text)
            continue
        _walk_rozetka_attrs(parsed, named, values)
    return named[0] if named else ""


def _rozetka_attr_values(*sources: Any) -> list[str]:
    """Усі текстові значення характеристик — щоб зіставити з кольором у наявності."""
    named: list[str] = []
    values: list[str] = []
    for src in sources:
        _walk_rozetka_attrs(src, named, values)
    return values


def _rozetka_purchase_blobs(purchase: dict[str, Any], item: dict[str, Any]) -> list[Any]:
    conf = purchase.get("conf") if isinstance(purchase.get("conf"), dict) else {}
    return [
        purchase.get("color"),
        item.get("color"),
        item.get("color_name"),
        item.get("details"),
        item.get("options"),
        item.get("item_details"),
        purchase.get("item_details"),
        purchase.get("details"),
        purchase.get("options"),
        purchase.get("conf_details"),
        conf.get("details"),
        conf.get("options"),
    ]


def _fetch_rozetka_item(token: str, item_id: Any) -> dict[str, Any]:
    iid = _trim(item_id)
    if not iid:
        return {}
    url = (
        f"https://api-seller.rozetka.com.ua/items/{iid}"
        "?expand=details,options,group_item"
    )
    status, data = _get_json(url, _rozetka_headers(token))
    if status < 200 or status >= 300 or not isinstance(data, dict):
        return {}
    content = data.get("content") if isinstance(data.get("content"), dict) else data
    return content if isinstance(content, dict) else {}


_ROZETKA_COLOR_ATTR_IDS: dict[str, set[str]] = {}
_ROZETKA_COLOR_VALUE_NAMES: dict[str, dict[str, str]] = {}


def _rozetka_color_attr_index(token: str, category_id: Any) -> tuple[set[str], dict[str, str]]:
    """id характеристики «Колір» та value_id → назва для категорії Rozetka."""
    cid = _trim(category_id)
    empty: tuple[set[str], dict[str, str]] = (set(), {})
    if not cid:
        return empty
    if cid in _ROZETKA_COLOR_ATTR_IDS:
        return _ROZETKA_COLOR_ATTR_IDS[cid], _ROZETKA_COLOR_VALUE_NAMES.get(cid) or {}
    url = (
        "https://api-seller.rozetka.com.ua/market-categories/category-options"
        f"?category_id={cid}"
    )
    status, data = _get_json(url, _rozetka_headers(token))
    ids: set[str] = set()
    value_names: dict[str, str] = {}
    content: Any = data.get("content") if isinstance(data, dict) else None
    rows: list[Any] = []
    if isinstance(content, list):
        rows = content
    elif isinstance(content, dict):
        for key in ("options", "attributes", "marketCategorys", "items"):
            if isinstance(content.get(key), list):
                rows = content.get(key) or []
                break
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _looks_like_color_attr(row.get("name")):
            continue
        oid = row.get("id")
        if oid is not None:
            ids.add(str(oid))
        vid = row.get("value_id")
        vname = _usable_color_text(row.get("value_name"))
        if vid is not None and vname:
            value_names[str(vid)] = vname
    _ROZETKA_COLOR_ATTR_IDS[cid] = ids
    _ROZETKA_COLOR_VALUE_NAMES[cid] = value_names
    return ids, value_names


def _color_from_details_ids(
    details: Any, attr_ids: set[str], value_names: dict[str, str]
) -> str:
    details = _parse_maybe_json(details)
    if not isinstance(details, dict) or not attr_ids:
        return ""
    for key, val in details.items():
        if str(key) not in attr_ids:
            continue
        text = _usable_color_text(val)
        if text:
            return text
        mapped = value_names.get(str(val).strip())
        if mapped:
            return mapped
    return ""


def _fill_rozetka_item_colors(mapped: dict[str, Any], token: str) -> None:
    for item in mapped.get("items") or []:
        if not isinstance(item, dict):
            continue
        if _trim(item.get("color")):
            continue
        content = _fetch_rozetka_item(token, item.get("item_id"))
        if not content:
            continue
        blobs = [
            content.get("color"),
            content.get("color_name"),
            content.get("details"),
            content.get("options"),
            content.get("group_item"),
        ]
        color = _extract_rozetka_color(*blobs)
        if not color:
            cat_id = content.get("catalog_id")
            cat = content.get("catalog_category")
            if isinstance(cat, dict):
                cat_id = cat_id or cat.get("id")
            attr_ids, value_names = _rozetka_color_attr_index(token, cat_id)
            color = _color_from_details_ids(
                content.get("details"), attr_ids, value_names
            ) or _color_from_details_ids(content.get("options"), attr_ids, value_names)
        extra_vals = _rozetka_attr_values(*blobs)
        if color:
            item["color"] = color
        prev = (
            item.get("color_candidates")
            if isinstance(item.get("color_candidates"), list)
            else []
        )
        item["color_candidates"] = list(dict.fromkeys([*prev, *extra_vals]))


def _fetch_prom_product(token: str, product_id: Any) -> dict[str, Any]:
    pid = _trim(product_id)
    if not pid:
        return {}
    status, data = _get_json(
        f"https://my.prom.ua/api/v1/products/{pid}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if status < 200 or status >= 300 or not isinstance(data, dict):
        return {}
    product = data.get("product") if isinstance(data.get("product"), dict) else data
    return product if isinstance(product, dict) else {}


def _fill_prom_item_meta(mapped: dict[str, Any], token: str) -> None:
    """Колір і код з картки товару Prom: в замовленні їх немає."""
    for item in mapped.get("items") or []:
        if not isinstance(item, dict):
            continue
        product = _fetch_prom_product(token, item.get("product_id"))
        if not product:
            continue
        if not _trim(item.get("code")):
            item["code"] = _prom_warehouse_code(
                product, _trim(item.get("product_id"))
            )
        blobs = [product.get("attributes")]
        color = _extract_rozetka_color(*blobs)
        extra_vals = _rozetka_attr_values(*blobs)
        name = _trim(product.get("name"))
        if name and name not in extra_vals:
            extra_vals.append(name)
        if color and not _trim(item.get("color")):
            item["color"] = color
        prev = (
            item.get("color_candidates")
            if isinstance(item.get("color_candidates"), list)
            else []
        )
        item["color_candidates"] = list(dict.fromkeys([*prev, *extra_vals]))
        if item.get("retail") in (None, ""):
            item["retail"] = product.get("price")


def _map_rozetka(content: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
    user = content.get("user") if isinstance(content.get("user"), dict) else {}
    delivery = content.get("delivery") if isinstance(content.get("delivery"), dict) else {}
    service = content.get("delivery_service") if isinstance(content.get("delivery_service"), dict) else {}
    items = []
    for p in _as_list(content.get("purchases")):
        if not isinstance(p, dict):
            continue
        item = p.get("item") if isinstance(p.get("item"), dict) else {}
        blobs = _rozetka_purchase_blobs(p, item)
        color = _extract_rozetka_color(*blobs)
        items.append(
            {
                "name": _pick(p.get("item_name"), item.get("name"), item.get("name_ua")),
                "code": _pick(item.get("article"), p.get("article"), item.get("id"), p.get("item_id")),
                "color": color,
                "color_candidates": _rozetka_attr_values(*blobs),
                "item_id": _pick(p.get("item_id"), item.get("id")),
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
        "carrier": (
            _carrier_label(
                service.get("name"),
                service.get("type"),
                delivery.get("delivery_service_name"),
            )
            or (
                "Розетка"
                if "w2w"
                in " ".join(
                    _trim(x).lower()
                    for x in (
                        service.get("name"),
                        service.get("type"),
                        delivery.get("delivery_service_name"),
                    )
                    if _trim(x)
                )
                else "НП"
            )
        ),
        "client": _client_line(
            city=_pick(
                _as_text(delivery.get("city"), "name_ua", "city_name", "title", "name"),
                delivery.get("city_title"),
            ),
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


def _rozetka_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _rozetka_error_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    err = data.get("errors")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or "").strip()
    if isinstance(err, str):
        return err.strip()
    return str(data.get("message") or "").strip()


def _rozetka_is_auth_error(status: int, data: Any) -> bool:
    if status in {401, 403}:
        return True
    blob = _rozetka_error_text(data).lower()
    return any(
        x in blob
        for x in (
            "invalid credentials",
            "unauthorized",
            "unauthenticated",
            "access denied",
            "token",
            "не авторизован",
        )
    )


def _rozetka_is_not_found(status: int, data: Any) -> bool:
    if status == 404:
        return True
    blob = _rozetka_error_text(data).lower()
    return any(
        x in blob
        for x in ("not_found", "not found", "не знайден", "не найден", "entity not found")
    )


def _rozetka_order_from_details(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    content = data.get("content")
    if not isinstance(content, dict) or not content.get("id"):
        return None
    if isinstance(content.get("orders"), list):
        return None
    return content


def _rozetka_order_from_search(data: Any, oid: str) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    content = data.get("content")
    if not isinstance(content, dict):
        return None
    orders = content.get("orders")
    if not isinstance(orders, list):
        return None
    for order in orders:
        if isinstance(order, dict) and str(order.get("id") or "") == oid:
            return order
    if len(orders) == 1 and isinstance(orders[0], dict) and orders[0].get("id"):
        return orders[0]
    return None


def _fetch_rozetka(source: dict[str, str], token: str, order_id: str) -> dict[str, Any] | None:
    oid = str(order_id).lstrip("#")
    expand = (
        "user,delivery,purchases,delivery_service,payment_type_name,"
        "status_data,item_details"
    )
    headers = _rozetka_headers(token)
    details_url = f"https://api-seller.rozetka.com.ua/orders/{oid}?expand={expand}"

    status, data = _get_json(details_url, headers)
    if _rozetka_is_auth_error(status, data):
        raise RuntimeError(
            "Rozetka: токен не принят или истёк. Обновите ROZETKA_API_TOKEN на Render"
        )
    if status >= 300 and not _rozetka_is_not_found(status, data):
        raise RuntimeError(
            f"Rozetka: {_rozetka_error_text(data) or f'HTTP {status}'}"
        )
    if (
        isinstance(data, dict)
        and data.get("success") is False
        and not _rozetka_is_not_found(status, data)
    ):
        raise RuntimeError(
            f"Rozetka: {_rozetka_error_text(data) or 'API вернула ошибку'}"
        )

    content = _rozetka_order_from_details(data) if 200 <= status < 300 else None

    if content is None:
        # GET /orders/{id} інколи не знаходить; search з types=1 — усі статуси
        search_url = (
            "https://api-seller.rozetka.com.ua/orders/search"
            f"?id={oid}&types=1&expand={expand}"
        )
        st2, data2 = _get_json(search_url, headers)
        if _rozetka_is_auth_error(st2, data2):
            raise RuntimeError(
                "Rozetka: токен не принят или истёк. Обновите ROZETKA_API_TOKEN на Render"
            )
        if 200 <= st2 < 300:
            content = _rozetka_order_from_search(data2, oid)
            if content and not content.get("purchases") and content.get("id"):
                st3, data3 = _get_json(
                    f"https://api-seller.rozetka.com.ua/orders/{content['id']}?expand={expand}",
                    headers,
                )
                detailed = _rozetka_order_from_details(data3)
                if detailed:
                    content = detailed

    if not content or not content.get("id"):
        return None
    mapped = _map_rozetka(content, source)
    try:
        _fill_rozetka_item_colors(mapped, token)
    except Exception:
        logger.exception("Rozetka item color enrich failed for order %s", content.get("id"))
    return mapped


def _map_kasta(order: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
    client = order.get("client") if isinstance(order.get("client"), dict) else {}
    addr = order.get("shipping_address") if isinstance(order.get("shipping_address"), dict) else {}
    delivery = order.get("delivery_properties") if isinstance(order.get("delivery_properties"), dict) else {}
    city_obj = addr.get("city") if isinstance(addr.get("city"), dict) else {}
    wh = addr.get("warehouse") if isinstance(addr.get("warehouse"), dict) else {}
    items_src = (
        _as_list(order.get("ordered_items"))
        or _as_list(order.get("items"))
        or _as_list(order.get("cancelled_items"))
        or _as_list(order.get("returned_items"))
    )
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
        try:
            qty = int(float(p.get("quantity") or 0))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            try:
                qty = int(float(p.get("original_quantity") or 1))
            except (TypeError, ValueError):
                qty = 1
        items.append(
            {
                "name": _pick(p.get("kind"), p.get("name"), p.get("title")),
                "code": code,
                "color": _pick(p.get("color"), p.get("kasta_color"), p.get("size")),
                "qty": max(1, qty),
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
    if len(sources) == 1:
        raise RuntimeError(
            f"{sources[0]['label']}: заказ {oid} не найден в кабинете продавца. "
            "Нужен ID заказа из seller.rozetka.com.ua, не ТТН и не номер из письма покупателю."
        )
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


def _lookup_item_catalog_meta(
    catalog: Any, code: str, color: str, product_id: str = ""
) -> tuple[str, str, str, str, str, str]:
    """Розташування, назва, РРЦ, дроп, колір і складський код з таблиці наявності."""
    if catalog is None or (not _trim(code) and not _trim(product_id)):
        return "", "", "", "", "", ""
    matches = _find_catalog_variants(catalog, code, color, product_id)
    if not matches:
        return "", "", "", "", "", ""
    v = matches[0]
    sheet_name = _trim(getattr(v, "warehouse_name", "")) or _trim(getattr(v, "name", ""))
    variant_color = _trim(getattr(v, "color", ""))
    if _is_generic_sheet_color(variant_color):
        variant_color = ""
    return (
        _real_location(getattr(v, "location", "")),
        sheet_name,
        _fmt_money(getattr(v, "retail_price", "")),
        _fmt_money(getattr(v, "drop_price", "")),
        variant_color,
        _trim(getattr(v, "code", "")),
    )


def build_sheet_rows(
    mapped: dict[str, Any],
    comment: str = "",
    *,
    catalog: Any = None,
    carrier_status: str = "",
) -> list[list[Any]]:
    items = mapped.get("items") or []
    if not items:
        items = [{"name": "", "code": "", "color": "", "qty": 1, "retail": ""}]
    note = _trim(comment)
    order_sum = _fmt_money(mapped.get("order_sum"))
    status_label = _trim(carrier_status) or _trim(mapped.get("status"))
    rows = []
    for item in items:
        code = _trim(item.get("code"))
        color = _trim(item.get("color"))
        product_id = _trim(item.get("product_id"))
        if not color and product_id:
            color = _lookup_unique_catalog_color(
                catalog, code, product_id=product_id
            )
        if not color:
            color = _match_catalog_color(
                catalog,
                code,
                item.get("color_candidates") or [],
                product_id=product_id,
            )
        if not color:
            color = _lookup_unique_catalog_color(catalog, code)
        (
            location,
            catalog_name,
            catalog_retail,
            catalog_drop,
            catalog_color,
            catalog_code,
        ) = _lookup_item_catalog_meta(catalog, code, color, product_id=product_id)
        if not color:
            color = catalog_color
        if (not code or _looks_like_prom_id(code)) and catalog_code:
            code = catalog_code
        item_name = catalog_name or _trim(item.get("name"))
        sale = catalog_retail or _fmt_money(item.get("retail"))
        if not sale and len(items) == 1:
            sale = order_sum
        drop = catalog_drop
        rows.append(
            [
                mapped.get("date") or "",
                mapped.get("order_id") or "",
                mapped.get("payment") or "",
                mapped.get("carrier") or "",
                item_name,
                code,
                color,
                item.get("qty") or 1,
                sale,
                drop,
                mapped.get("source_label") or "",
                mapped.get("client") or "",
                mapped.get("ttn") or "",
                status_label,
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
    ttn = _trim(mapped.get("ttn"))
    carrier_status = ""
    if ttn:
        try:
            from bot.sheet_tracking import lookup_single_ttn_status

            carrier_status = lookup_single_ttn_status(storage, ttn)
        except Exception:
            pass
    rows = build_sheet_rows(
        mapped, comment, catalog=catalog, carrier_status=carrier_status
    )
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

    # Списання залишків з таблиці наявності для нового замовлення
    stock_res = None
    if catalog and hasattr(catalog, "consume_cart_stock"):
        try:
            stock_res = catalog.consume_cart_stock(
                mapped.get("items") or [], allow_insufficient=True
            )
        except Exception:
            logger.exception(
                "Не вдалося списати залишки для замовлення маркетплейсу %s",
                mapped.get("order_id"),
            )

    msg = f"Записано {len(rows)} стр. заказа {mapped['order_id']}"
    if stock_res and stock_res.get("updated_rows"):
        msg += f" (списано остатки в {stock_res['updated_rows']} стр. наличия)"

    return {
        "ok": True,
        "already": False,
        "updated": False,
        "source": {"id": mapped["source_id"], "label": mapped["source_label"]},
        "orderId": mapped["order_id"],
        "preview": preview_rows(rows),
        "rows": written,
        "stock": stock_res,
        "message": msg,
    }


MANUAL_ORDER_PREFIX = "TEL-"


def lookup_catalog_items(
    catalog: Any, query: str, *, limit: int = 40
) -> list[dict[str, Any]]:
    """Пошук у таблиці наявності для ручної форми розширення."""
    q = _trim(query)
    if not q or catalog is None:
        return []
    variants: list[Any] = []
    if hasattr(catalog, "search"):
        variants = catalog.search(query=q, mode="code", limit=limit) or []
        if not variants:
            variants = catalog.search(query=q, mode="auto", limit=limit) or []
    out: list[dict[str, Any]] = []
    for v in variants[:limit]:
        data = v.to_dict() if hasattr(v, "to_dict") else {}
        out.append(
            {
                "code": _trim(data.get("code")),
                "name": _trim(data.get("name")),
                "color": _trim(data.get("color")),
                "stock": data.get("stock"),
                "drop_price": _fmt_money(data.get("drop_price")),
                "retail_price": _fmt_money(data.get("retail_price")),
                "location": _real_location(data.get("location")),
            }
        )
    return out


def next_manual_order_id(ws: Any) -> str:
    col = ws.col_values(COL_ORDER_NO)
    max_n = 0
    prefix = MANUAL_ORDER_PREFIX.upper()
    for value in col[1:]:
        text = _trim(value).upper()
        if not text.startswith(prefix):
            continue
        suffix = text[len(prefix) :].lstrip()
        if suffix.isdigit():
            max_n = max(max_n, int(suffix))
    return f"{MANUAL_ORDER_PREFIX}{max_n + 1:04d}"


def write_manual_order(
    storage: AppStorage,
    *,
    code: str,
    color: str = "",
    qty: int = 1,
    name: str = "",
    client_name: str = "",
    phone: str = "",
    city: str = "",
    warehouse: str = "",
    payment: str = "НАЛОЖКА",
    carrier: str = "НП",
    ttn: str = "",
    source: str = "Телефон",
    comment: str = "",
    catalog: Any = None,
) -> dict[str, Any]:
    code = _trim(code)
    if not code:
        raise ValueError("Вкажіть код товару")
    qty = max(1, int(qty or 1))
    color = _trim(color)
    name = _trim(name)
    ttn = re.sub(r"\s+", "", _trim(ttn))
    source_label = _trim(source) or "Телефон"
    pay = _payment_label(payment) or "НАЛОЖКА"
    ship = _carrier_label(carrier) or _trim(carrier) or "НП"
    client_name = _trim(client_name)
    phone = _trim(phone)
    city = _trim(city)
    warehouse = _trim(warehouse)

    ttn_details: dict[str, Any] = {}
    if ttn:
        try:
            from bot.sheet_tracking import lookup_ttn_details

            ttn_details = lookup_ttn_details(storage, ttn)
        except Exception:
            logger.exception("NP TTN lookup failed for manual order")
            ttn_details = {}
        if not client_name:
            client_name = _trim(ttn_details.get("name"))
        if not phone:
            phone = _trim(ttn_details.get("phone"))
        if not city:
            city = _trim(ttn_details.get("city"))
        if not warehouse:
            warehouse = _trim(ttn_details.get("warehouse"))
        if not ship or ship == "НП":
            # Готова ТТН НП — служба вже відома
            if ttn_details.get("found"):
                ship = _carrier_label(carrier) or "НП"

    ws = _open_orders_worksheet(storage)
    order_id = next_manual_order_id(ws)

    carrier_status = _trim(ttn_details.get("status"))
    if ttn:
        if not carrier_status:
            carrier_status = "ТТН надано"
    else:
        carrier_status = "немає ТТН"

    mapped = {
        "source_id": "manual",
        "source_label": source_label,
        "order_id": order_id,
        "date": datetime.now(KYIV).strftime("%d.%m.%Y"),
        "payment": pay,
        "carrier": ship,
        "client": _client_line(
            city=city,
            place=warehouse,
            name=client_name,
            phone=phone,
        ),
        "ttn": ttn,
        "status": carrier_status,
        "order_sum": "",
        "items": [
            {
                "name": name,
                "code": code,
                "color": color,
                "qty": qty,
                "retail": "",
            }
        ],
    }
    rows = build_sheet_rows(
        mapped, comment, catalog=catalog, carrier_status=carrier_status
    )
    written = append_order_rows(ws, rows)

    stock_res = None
    if catalog and hasattr(catalog, "consume_cart_stock"):
        try:
            stock_res = catalog.consume_cart_stock(
                mapped.get("items") or [], allow_insufficient=True
            )
        except Exception:
            logger.exception(
                "Не вдалося списати залишки для ручного замовлення %s", order_id
            )

    msg = f"Записано {len(rows)} стр. заказа {order_id}"
    if stock_res and stock_res.get("updated_rows"):
        msg += f" (списано остатки в {stock_res['updated_rows']} стр. наличия)"

    return {
        "ok": True,
        "already": False,
        "updated": False,
        "source": {"id": "manual", "label": source_label},
        "orderId": order_id,
        "preview": preview_rows(rows),
        "rows": written,
        "stock": stock_res,
        "message": msg,
    }
