"""Клиент API Нової Пошти (поиск городов и отделений)."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"
_WAREHOUSE_QUERY_PREFIX_RE = re.compile(
    r"^(?:№|#|no\.?|nº)?\s*(?:відділення|отделение|поштомат|почтомат)?\s*",
    re.IGNORECASE,
)


@dataclass
class SettlementOption:
    present: str
    main_description: str
    area: str
    region: str
    settlement_ref: str
    city_ref: str
    warehouses_count: int | None = None

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "main_description": self.main_description,
            "area": self.area,
            "region": self.region,
            "settlement_ref": self.settlement_ref,
            "city_ref": self.city_ref,
            "warehouses_count": self.warehouses_count,
            "label": self.present or self.main_description,
        }


@dataclass
class WarehouseOption:
    ref: str
    description: str
    description_ru: str
    number: str
    city_ref: str
    category: str
    category_label: str = ""

    def to_dict(self) -> dict:
        label = self.description or self.description_ru or self.number
        cat = self.category_label or self.category
        if cat and label and not label.lower().startswith(cat.lower()):
            display = f"[{cat}] {label}"
        else:
            display = label
        return {
            "ref": self.ref,
            "description": self.description,
            "description_ru": self.description_ru,
            "number": self.number,
            "city_ref": self.city_ref,
            "category": self.category,
            "category_label": cat,
            "label": display,
        }


def _warehouse_category_label(raw: str) -> str:
    key = (raw or "").strip().casefold()
    mapping = {
        "branch": "Відділення",
        "postomat": "Поштомат",
        "store": "Пункт видачі/прийому",
        "mobile": "Мобільне відділення",
        "cargo": "Вантажне відділення",
        "postoffice": "Відділення",
    }
    for needle, label in mapping.items():
        if needle in key:
            return label
    if not raw:
        return "Відділення"
    return raw


def _normalize_warehouse_query(query: str) -> str:
    q = (query or "").strip()
    q = _WAREHOUSE_QUERY_PREFIX_RE.sub("", q).strip()
    return q


def _warehouse_match_rank(query: str, number: str, description: str) -> int:
    """Менше = краще. 0 = точний номер."""
    q = (query or "").strip().casefold()
    if not q:
        return 100
    num = (number or "").strip().casefold()
    desc = (description or "").strip().casefold()
    if num and num == q:
        return 0
    q_digits = q.lstrip("0") or "0"
    num_digits = num.lstrip("0") or "0"
    if num and q.isdigit() and num_digits == q_digits:
        return 1
    if num and num.startswith(q):
        return 10 + (len(num) - len(q))
    if q in desc:
        return 30 + desc.find(q)
    return 80


def _row_to_warehouse(row: dict, city_ref: str) -> WarehouseOption | None:
    if not _warehouse_is_selectable(row):
        return None
    ref = str(row.get("Ref") or "").strip()
    if not ref:
        return None
    category = str(
        row.get("CategoryOfWarehouse") or row.get("TypeOfWarehouse") or ""
    ).strip()
    desc = str(row.get("Description") or "").strip()
    if "мобільн" in desc.casefold() or "мобильн" in desc.casefold():
        category_label = "Мобільне відділення"
    else:
        category_label = _warehouse_category_label(category)
    return WarehouseOption(
        ref=ref,
        description=desc,
        description_ru=str(row.get("DescriptionRu") or "").strip(),
        number=str(row.get("Number") or "").strip(),
        city_ref=str(row.get("CityRef") or city_ref).strip(),
        category=category,
        category_label=category_label,
    )


def _warehouse_is_selectable(row: dict) -> bool:
    """Відсікаємо явно недоступні точки, решту (в т.ч. пункти прийому) показуємо."""
    deny = str(row.get("DenyToSelect") or "").strip().lower()
    if deny in {"1", "true", "yes"}:
        return False
    status = str(row.get("WarehouseStatus") or row.get("Status") or "").strip().casefold()
    if status in {"inoperative", "closed", "не працює", "закрыт"}:
        return False
    return True


@dataclass
class StreetOption:
    ref: str
    description: str
    present: str
    settlement_ref: str

    def to_dict(self) -> dict:
        label = self.present or self.description
        return {
            "ref": self.ref,
            "description": self.description,
            "present": self.present,
            "settlement_ref": self.settlement_ref,
            "label": label,
        }


class NovaPoshtaError(Exception):
    pass


class NovaPoshtaClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or os.getenv("NOVA_POSHTA_API_KEY", "")).strip()

    def configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, model_name: str, called_method: str, props: dict[str, Any]) -> Any:
        if not self.api_key:
            raise NovaPoshtaError("NOVA_POSHTA_API_KEY не задан")

        payload = {
            "apiKey": self.api_key,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": props,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            NP_API_URL,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            logger.exception("Nova Poshta HTTP error")
            raise NovaPoshtaError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            logger.exception("Nova Poshta network error")
            raise NovaPoshtaError("Мережева помилка Nova Poshta") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NovaPoshtaError("Некоректна відповідь Nova Poshta") from exc

        if not data.get("success"):
            errors = data.get("errors") or data.get("errorCodes") or ["unknown"]
            raise NovaPoshtaError("; ".join(str(e) for e in errors))

        return data.get("data") or []

    def search_settlements(self, query: str, limit: int = 20) -> list[SettlementOption]:
        query = (query or "").strip()
        if len(query) < 2:
            return []

        data = self._request(
            "Address",
            "searchSettlements",
            {
                "CityName": query,
                "Limit": str(max(1, min(limit, 50))),
                "Page": "1",
            },
        )
        if not data:
            return []

        # data[0].Addresses — типова структура searchSettlements
        block = data[0] if isinstance(data[0], dict) else {}
        addresses = block.get("Addresses") or []
        results: list[SettlementOption] = []
        for row in addresses:
            settlement_ref = str(row.get("Ref") or "").strip()
            city_ref = str(row.get("DeliveryCity") or "").strip()
            if not settlement_ref or not city_ref:
                continue
            present = str(row.get("Present") or "").strip()
            main = str(row.get("MainDescription") or "").strip()
            area = str(row.get("Area") or "").strip()
            region = str(row.get("Region") or "").strip()
            wh = row.get("Warehouses")
            try:
                wh_count = int(wh) if wh is not None and str(wh).strip() != "" else None
            except (TypeError, ValueError):
                wh_count = None
            results.append(
                SettlementOption(
                    present=present or main,
                    main_description=main,
                    area=area,
                    region=region,
                    settlement_ref=settlement_ref,
                    city_ref=city_ref,
                    warehouses_count=wh_count,
                )
            )
        return results

    def search_warehouses(
        self,
        city_ref: str,
        query: str = "",
        limit: int = 30,
    ) -> list[WarehouseOption]:
        city_ref = (city_ref or "").strip()
        if not city_ref:
            return []

        q = _normalize_warehouse_query(query)
        max_items = max(1, min(int(limit or 30), 100))
        # Один запит до NP: Limit = скільки реально треба, без зайвих сторінок
        page_size = max_items
        props: dict[str, Any] = {
            "CityRef": city_ref,
            "Limit": str(page_size),
            "Page": "1",
        }
        if q:
            props["FindByString"] = q

        data = self._request("Address", "getWarehouses", props) or []
        results: list[WarehouseOption] = []
        seen: set[str] = set()
        for row in data:
            if not isinstance(row, dict):
                continue
            item = _row_to_warehouse(row, city_ref)
            if item is None or item.ref in seen:
                continue
            seen.add(item.ref)
            results.append(item)

        if q:
            results.sort(
                key=lambda w: (
                    _warehouse_match_rank(q, w.number, w.description),
                    w.number.zfill(6),
                    w.description.casefold(),
                )
            )
            # Точний номер («10» / «№10») — не тягнемо зайві 30 пунктів
            exact = [
                w
                for w in results
                if _warehouse_match_rank(q, w.number, w.description) <= 1
            ]
            if exact and (q.isdigit() or q.casefold() in {w.number.casefold() for w in exact}):
                return exact[:max_items]

        return results[:max_items]

    def search_streets(
        self,
        settlement_ref: str,
        query: str,
        city_ref: str = "",
        limit: int = 20,
    ) -> list[StreetOption]:
        settlement_ref = (settlement_ref or "").strip()
        city_ref = (city_ref or "").strip()
        query = (query or "").strip()
        if len(query) < 2:
            return []
        if not settlement_ref and not city_ref:
            return []

        results: list[StreetOption] = []

        if settlement_ref:
            try:
                data = self._request(
                    "Address",
                    "searchSettlementStreets",
                    {
                        "StreetName": query,
                        "SettlementRef": settlement_ref,
                        "Limit": str(max(1, min(limit, 50))),
                    },
                )
                block = data[0] if data and isinstance(data[0], dict) else {}
                addresses = block.get("Addresses") or []
                for row in addresses:
                    if not isinstance(row, dict):
                        continue
                    ref = str(
                        row.get("SettlementStreetRef") or row.get("Ref") or ""
                    ).strip()
                    if not ref:
                        continue
                    present = str(row.get("Present") or "").strip()
                    description = str(
                        row.get("SettlementStreetDescription")
                        or row.get("Description")
                        or ""
                    ).strip()
                    street_type = str(
                        row.get("StreetsTypeDescription")
                        or row.get("StreetsType")
                        or ""
                    ).strip()
                    if not present and description:
                        present = f"{street_type} {description}".strip()
                    results.append(
                        StreetOption(
                            ref=ref,
                            description=description or present,
                            present=present or description,
                            settlement_ref=str(
                                row.get("SettlementRef") or settlement_ref
                            ).strip(),
                        )
                    )
            except NovaPoshtaError:
                logger.warning("searchSettlementStreets failed, fallback to getStreet")

        if not results and city_ref:
            data = self._request(
                "Address",
                "getStreet",
                {
                    "CityRef": city_ref,
                    "FindByString": query,
                    "Limit": str(max(1, min(limit, 50))),
                    "Page": "1",
                },
            )
            for row in data:
                ref = str(row.get("Ref") or "").strip()
                if not ref:
                    continue
                description = str(row.get("Description") or "").strip()
                description_ru = str(row.get("DescriptionRu") or "").strip()
                street_type = str(
                    row.get("StreetsTypeDescription")
                    or row.get("StreetsType")
                    or ""
                ).strip()
                label = description or description_ru
                if street_type and label and not label.lower().startswith(street_type.lower()):
                    label = f"{street_type} {label}".strip()
                results.append(
                    StreetOption(
                        ref=ref,
                        description=description or description_ru,
                        present=label,
                        settlement_ref=settlement_ref,
                    )
                )

        return results[:limit]
