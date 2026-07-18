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


def _code_raw(code: str) -> str:
    return str(code or "").strip().lstrip("'").casefold()


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


def _code_relevance(query: str, code: str) -> int | None:
    """
    Оцінка релевантності коду (менше = краще).
    None = не підходить.
    """
    q_raw = _code_raw(query)
    c_raw = _code_raw(code)
    q_norm = _normalize_code(query).casefold()
    c_norm = _normalize_code(code).casefold()
    if not q_raw and not q_norm:
        return None

    if q_raw and c_raw == q_raw:
        return 0
    if q_norm and c_norm == q_norm:
        return 1
    if q_raw and c_raw.startswith(q_raw):
        return 10 + (len(c_raw) - len(q_raw))
    if q_norm and c_norm.startswith(q_norm):
        return 20 + (len(c_norm) - len(q_norm))
    if q_raw and q_raw in c_raw:
        return 40 + c_raw.find(q_raw)
    if q_norm and q_norm in c_norm:
        return 50 + c_norm.find(q_norm)
    return None


def _name_relevance(query: str, name: str) -> int | None:
    needle = _norm_text(query)
    hay = _norm_text(name)
    if not needle:
        return None
    if hay == needle:
        return 0
    if hay.startswith(needle):
        return 10
    if needle in hay:
        return 20 + hay.find(needle)
    # усі слова запиту є в назві
    words = [w for w in needle.split() if w]
    if words and all(w in hay for w in words):
        return 30
    return None


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

    def list_colors(self, query: str = "", limit: int = 40) -> list[str]:
        self.refresh()
        needle = _norm_text(query)
        with self._lock:
            colors = sorted(
                {v.color.strip() for v in self._variants if v.color and v.color.strip()},
                key=lambda c: c.casefold(),
            )
        if not needle:
            return colors[: max(1, min(limit, 200))]
        scored: list[tuple[int, str]] = []
        for color in colors:
            n = _norm_text(color)
            if n == needle:
                scored.append((0, color))
            elif n.startswith(needle):
                scored.append((1, color))
            elif needle in n:
                scored.append((2, color))
        scored.sort(key=lambda x: (x[0], x[1].casefold()))
        return [c for _, c in scored[: max(1, min(limit, 200))]]

    def search_by_code(self, query: str) -> list[ProductVariant]:
        """Совместимость: поиск по коду (точное + частичное)."""
        return self.search(query=query, color="", mode="code")

    def search(
        self,
        query: str = "",
        color: str = "",
        limit: int = 80,
        mode: str = "auto",
    ) -> list[ProductVariant]:
        """
        Гибридный поиск с ранжированием:
        - код: точний → починається з → містить (010 → 010, 010T, 010TK)
        - назва: точна → починається з → містить
        - опційний фільтр кольору
        """
        self.refresh()
        needle = _norm_text(query)
        color_needle = _norm_text(color)
        if not needle and not color_needle:
            return []

        with self._lock:
            variants = list(self._variants)

        ranked: list[tuple[tuple[int, int, str], ProductVariant]] = []
        for v in variants:
            if color_needle and color_needle not in _norm_text(v.color):
                continue

            if not needle:
                ranked.append(((90, 0, v.code.casefold()), v))
                continue

            code_score = None
            name_score = None
            if mode in {"auto", "code"}:
                code_score = _code_relevance(query, v.code)
            if mode in {"auto", "name"}:
                name_score = _name_relevance(query, v.name)

            if code_score is None and name_score is None:
                continue

            # Код важливіший за назву; всередині — за релевантністю
            if code_score is not None:
                sort_key = (0, code_score, v.code.casefold())
            else:
                sort_key = (1, name_score or 99, v.name.casefold())
            ranked.append((sort_key, v))

        ranked.sort(key=lambda item: item[0])

        seen: set[str] = set()
        results: list[ProductVariant] = []
        for _, item in ranked:
            key = f"{item.product_id}|{item.code}|{item.color}"
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= max(1, min(limit, 200)):
                break
        return results
