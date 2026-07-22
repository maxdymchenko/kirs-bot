"""Клиент API Нової Пошти (поиск городов и отделений)."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
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

    # --- Відправник / ТТН / трекінг ---

    def get_counterparties(self, property_kind: str = "Sender") -> list[dict[str, Any]]:
        data = self._request(
            "Counterparty",
            "getCounterparties",
            {"CounterpartyProperty": property_kind, "Page": "1"},
        )
        return [row for row in (data or []) if isinstance(row, dict)]

    def get_counterparty_contact_persons(self, counterparty_ref: str) -> list[dict[str, Any]]:
        ref = (counterparty_ref or "").strip()
        if not ref:
            return []
        data = self._request(
            "Counterparty",
            "getCounterpartyContactPersons",
            {"Ref": ref, "Page": "1"},
        )
        return [row for row in (data or []) if isinstance(row, dict)]

    def get_counterparty_addresses(
        self, counterparty_ref: str, property_kind: str = "Sender"
    ) -> list[dict[str, Any]]:
        ref = (counterparty_ref or "").strip()
        if not ref:
            return []
        data = self._request(
            "Counterparty",
            "getCounterpartyAddresses",
            {
                "Ref": ref,
                "CounterpartyProperty": property_kind,
            },
        )
        return [row for row in (data or []) if isinstance(row, dict)]

    def create_internet_document(self, props: dict[str, Any]) -> dict[str, Any]:
        data = self._request("InternetDocument", "save", props) or []
        if not data or not isinstance(data[0], dict):
            raise NovaPoshtaError("Порожня відповідь при створенні ТТН")
        row = data[0]
        number = str(row.get("IntDocNumber") or "").strip()
        if not number:
            raise NovaPoshtaError("НП не повернула номер ТТН")
        return {
            "ttn_number": number,
            "ref": str(row.get("Ref") or "").strip(),
            "cost_on_site": row.get("CostOnSite"),
            "estimated_delivery_date": row.get("EstimatedDeliveryDate"),
            "raw": row,
        }

    def get_status_documents(
        self, documents: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """
        documents: [{DocumentNumber, Phone?}, ...]
        """
        docs = []
        for item in documents:
            number = str((item or {}).get("DocumentNumber") or "").strip()
            if not number:
                continue
            entry: dict[str, str] = {"DocumentNumber": number}
            phone = str((item or {}).get("Phone") or "").strip()
            if phone:
                entry["Phone"] = phone
            docs.append(entry)
        if not docs:
            return []
        data = self._request(
            "TrackingDocument",
            "getStatusDocuments",
            {"Documents": docs},
        )
        return [row for row in (data or []) if isinstance(row, dict)]


def map_np_status_code(status_code: str | int | None, status_text: str = "") -> str:
    """Уніфікований внутрішній статус за StatusCode НП."""
    code = str(status_code or "").strip()
    text = str(status_text or "").casefold()
    # Отримано / гроші по налогу в дорозі / видані відправнику
    if code in {"9", "10", "11"}:
        return "received"
    # Відмова від отримання (клієнт не забрав)
    if code in {"102", "103", "104", "105", "106", "108"}:
        return "refused"
    # Повернення відправнику / утилізація тощо
    if code in {"111"}:
        return "returned"
    if code in {"2", "3"}:
        return "failed"
    if code in {"7", "8"}:
        return "at_warehouse"
    # Код 6 у деяких джерелах — повернення; перевіряємо текст
    if code == "6" and any(w in text for w in ("поверн", "відмов", "отказ", "возврат")):
        if any(w in text for w in ("відмов", "отказ", "refuse")):
            return "refused"
        return "returned"
    if code in {"4", "5", "6", "41", "101"}:
        return "in_transit"
    if code in {"1"}:
        return "created"
    if any(w in text for w in ("отримано", "получен")):
        return "received"
    if any(w in text for w in ("відмов", "отказ", "refuse")):
        return "refused"
    if any(w in text for w in ("поверн", "возврат")):
        return "returned"
    return "in_transit" if code else "unknown"


def extract_warehouse_arrival_iso(row: dict[str, Any] | None) -> str:
    """Дата прибуття на відділення з відповіді трекінгу (якщо є)."""
    if not isinstance(row, dict):
        return ""
    for key in (
        "RecipientDateTime",
        "DateReceived",
        "ActualDeliveryDate",
        "ScheduledDeliveryDate",
        "DateScan",
    ):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        # НП часто дає dd.mm.yyyy [HH:MM:SS]
        for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw[:19], fmt).isoformat(timespec="seconds")
            except ValueError:
                continue
    return ""


def extract_delivery_cost(row: dict[str, Any] | None, order: dict[str, Any] | None = None) -> float:
    """Вартість доставки з трекінгу або з payload після створення ТТН."""
    candidates: list[Any] = []
    if isinstance(row, dict):
        for key in (
            "DocumentCost",
            "DeliveryCost",
            "CostOnSite",
            "SettlementCost",
            "ShippingCost",
        ):
            if row.get(key) not in (None, ""):
                candidates.append(row.get(key))
    payload = (order or {}).get("payload") or {}
    if payload.get("np_cost_on_site") not in (None, ""):
        candidates.append(payload.get("np_cost_on_site"))
    if payload.get("np_delivery_cost") not in (None, ""):
        candidates.append(payload.get("np_delivery_cost"))
    for raw in candidates:
        try:
            value = float(str(raw).replace(",", ".").strip())
        except (TypeError, ValueError):
            continue
        if value > 0:
            return round(value, 2)
    return 0.0
