"""Каталог товаров из Google Sheets (таблица наличия)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

DEFAULT_SHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@dataclass
class ProductVariant:
    product_id: str
    code: str
    name: str
    color: str
    stock: int | None
    drop_price: str
    photo_url: str

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "code": self.code,
            "name": self.name,
            "color": self.color,
            "stock": self.stock,
            "drop_price": self.drop_price,
            "photo_url": self.photo_url,
        }


def _normalize_code(code: str) -> str:
    code = str(code).strip().lstrip("'")
    return code.lstrip("0") or "0"


def _parse_stock(raw: str) -> int | None:
    raw = str(raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _norm_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


class CatalogService:
    def __init__(
        self,
        spreadsheet_id: str | None = None,
        credentials_path: str | Path | None = None,
        cache_ttl_seconds: int = 30,
    ):
        self.spreadsheet_id = spreadsheet_id or os.getenv(
            "STOCK_SPREADSHEET_ID", DEFAULT_SHEET_ID
        )
        self.credentials_path = Path(
            credentials_path
            or os.getenv(
                "GOOGLE_CREDENTIALS_FILE",
                Path(__file__).resolve().parent.parent
                / "midyear-respect-502706-i6-c5ddff36cd28.json",
            )
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self._lock = Lock()
        self._variants: list[ProductVariant] = []
        self._loaded_at = 0.0

    def _build_client(self) -> gspread.Client:
        json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        if json_env:
            import json

            info = json.loads(json_env)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Файл credentials не найден: {self.credentials_path}. "
                    "Задайте GOOGLE_CREDENTIALS_FILE или GOOGLE_CREDENTIALS_JSON"
                )
            creds = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=SCOPES
            )
        return gspread.authorize(creds)

    def refresh(self, force: bool = False) -> None:
        with self._lock:
            now = time.time()
            if not force and self._variants and now - self._loaded_at < self.cache_ttl_seconds:
                return

            client = self._build_client()
            ws = client.open_by_key(self.spreadsheet_id).sheet1
            rows = ws.get_all_values()
            variants: list[ProductVariant] = []

            # A ID, B код, C название, E цвет, F наличиеличие, G дроп-цена, M фото
            for row in rows[1:]:
                while len(row) < 13:
                    row.append("")
                product_id = str(row[0]).strip()
                code = str(row[1]).strip().lstrip("'")
                name = str(row[2]).strip()
                color = str(row[4]).strip()
                if not code or not name:
                    continue
                variants.append(
                    ProductVariant(
                        product_id=product_id,
                        code=code,
                        name=name,
                        color=color,
                        stock=_parse_stock(row[5]),
                        drop_price=str(row[6]).strip(),
                        photo_url=str(row[12]).strip(),
                    )
                )

            self._variants = variants
            self._loaded_at = now
            logger.info("Каталог загружен: %d позиций", len(variants))

    def list_colors(self) -> list[str]:
        self.refresh()
        with self._lock:
            colors = sorted(
                {v.color.strip() for v in self._variants if v.color and v.color.strip()},
                key=lambda c: c.casefold(),
            )
        return colors

    def search_by_code(self, query: str) -> list[ProductVariant]:
        """Совместимость: точный поиск по коду."""
        return self.search(query=query, color="", mode="code")

    def search(
        self,
        query: str = "",
        color: str = "",
        limit: int = 80,
        mode: str = "auto",
    ) -> list[ProductVariant]:
        """
        Гибридный поиск:
        - по коду (точное совпадение после нормализации нулей)
        - по названию (полное и частичное, регистронезависимо)
        - опциональный фильтр по цвету
        """
        self.refresh()
        needle = _norm_text(query)
        color_needle = _norm_text(color)
        if not needle and not color_needle:
            return []

        with self._lock:
            variants = list(self._variants)

        code_hits: list[ProductVariant] = []
        name_exact: list[ProductVariant] = []
        name_partial: list[ProductVariant] = []

        for v in variants:
            if color_needle and color_needle not in _norm_text(v.color):
                continue

            if not needle:
                name_partial.append(v)
                continue

            code_norm = _normalize_code(v.code)
            query_code = _normalize_code(query)
            name_norm = _norm_text(v.name)

            if mode in {"auto", "code"} and query_code and code_norm == query_code:
                code_hits.append(v)
                continue

            if mode in {"auto", "name"}:
                if name_norm == needle:
                    name_exact.append(v)
                elif needle in name_norm:
                    name_partial.append(v)

        # Приоритет: точный код → точное имя → частичное имя
        seen: set[str] = set()
        results: list[ProductVariant] = []
        for group in (code_hits, name_exact, name_partial):
            for item in group:
                key = f"{item.product_id}|{item.code}|{item.color}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                if len(results) >= max(1, min(limit, 200)):
                    return results
        return results
