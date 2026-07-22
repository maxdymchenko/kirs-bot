"""Каталог товаров из Google Sheets (таблица наличия)."""

from __future__ import annotations

import logging
import os
import re
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

# Роздільники в кодах комплектів: "010 + 009K", "010+009К", "010/009K"
_CODE_TOKEN_SPLIT_RE = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)


@dataclass
class ProductVariant:
    product_id: str
    code: str
    name: str
    color: str
    stock: int | None
    drop_price: str
    photo_url: str
    live_photo_url: str = ""

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "code": self.code,
            "name": self.name,
            "color": self.color,
            "stock": self.stock,
            "drop_price": self.drop_price,
            "photo_url": self.photo_url,
            "live_photo_url": self.live_photo_url,
        }


def _normalize_code(code: str) -> str:
    code = str(code).strip().lstrip("'")
    return code.lstrip("0") or "0"


def _extract_url(raw: str) -> str:
    """URL з тексту або з формули =HYPERLINK("url"; "label")."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    match = re.search(r'HYPERLINK\s*\(\s*"([^"]+)"', text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"HYPERLINK\s*\(\s*'([^']+)'", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_url_from_cell_meta(cell: dict | None) -> str:
    """
    URL з метаданих комірки Sheets API:
    - класичний hyperlink
    - smart chip / rich link (chipRuns)
    - формула HYPERLINK / прямий URL у тексті
    """
    if not cell:
        return ""
    hyperlink = str(cell.get("hyperlink") or "").strip()
    if hyperlink.startswith(("http://", "https://")):
        return hyperlink
    for run in cell.get("chipRuns") or []:
        chip = (run or {}).get("chip") or {}
        props = chip.get("richLinkProperties") or {}
        uri = str(props.get("uri") or "").strip()
        if uri.startswith(("http://", "https://")):
            return uri
    entered = cell.get("userEnteredValue") or {}
    if "formulaValue" in entered:
        found = _extract_url(str(entered.get("formulaValue") or ""))
        if found:
            return found
    for key in ("formattedValue", "stringValue"):
        raw = cell.get(key)
        if raw is None and key == "stringValue":
            raw = entered.get("stringValue")
        found = _extract_url(str(raw or ""))
        if found:
            return found
    return ""


def _fetch_live_photo_urls(
    client: gspread.Client, spreadsheet_id: str, sheet_title: str, rows_count: int
) -> list[str]:
    """Список URL колонки N, вирівняний по рядках даних (індекс 0 = рядок 2)."""
    if rows_count <= 0:
        return []
    end_row = rows_count + 1  # N2:N{end_row}
    # Екрануємо назву аркуша для A1-нотації
    safe_title = str(sheet_title or "Sheet1").replace("'", "''")
    range_a1 = f"'{safe_title}'!N2:N{end_row}"
    try:
        resp = client.http_client.request(
            "get",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
            params={
                "ranges": range_a1,
                "includeGridData": "true",
                "fields": (
                    "sheets.data.rowData.values("
                    "userEnteredValue,formattedValue,hyperlink,chipRuns"
                    ")"
                ),
            },
        )
        payload = resp.json() if hasattr(resp, "json") else resp
        row_data = (
            (((payload.get("sheets") or [{}])[0].get("data") or [{}])[0].get("rowData"))
            or []
        )
    except Exception:
        logger.exception("Не вдалося прочитати rich-link колонки N (живі фото)")
        return [""] * rows_count

    urls: list[str] = []
    for idx in range(rows_count):
        cell = None
        if idx < len(row_data):
            values = (row_data[idx] or {}).get("values") or []
            cell = values[0] if values else None
        urls.append(_extract_url_from_cell_meta(cell))
    return urls


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


def _code_tokens(code: str) -> list[str]:
    """Частини коду комплекту: '010 + 009K' → ['010', '009K']."""
    raw = str(code or "").strip().lstrip("'")
    if not raw:
        return []
    return [t for t in _CODE_TOKEN_SPLIT_RE.split(raw) if t]


def _token_relevance(query: str, token: str) -> int | None:
    """
    Точний / префіксний збіг одного токена коду.
    Без «голого» norm-startswith (інакше 010 → 110 через '10').
    """
    q_raw = _code_raw(query)
    t_raw = _code_raw(token)
    q_norm = _normalize_code(query).casefold()
    t_norm = _normalize_code(token).casefold()
    if not q_raw and not q_norm:
        return None

    if q_raw and t_raw == q_raw:
        return 0
    if q_norm and t_norm == q_norm:
        return 1
    if q_raw and t_raw.startswith(q_raw):
        return 10 + (len(t_raw) - len(q_raw))
    return None


def _code_relevance(query: str, code: str) -> int | None:
    """
    Оцінка релевантності коду (менше = краще).
    None = не підходить.

    Порядок:
    0–1   точний код (010)
    10+   префікс цілого коду (010T, 010TK)
    60+   токен у комплекті (010 + 009K, 009K + 010) — менш релевантно
    Голий 009K за запитом 010 — не потрапляє.
    """
    q_raw = _code_raw(query)
    q_norm = _normalize_code(query).casefold()
    if not q_raw and not q_norm:
        return None

    tokens = _code_tokens(code)
    if not tokens:
        return None

    best: int | None = None

    # Цілий рядок коду (звичайні артикули 010 / 010T)
    full = _token_relevance(query, code.strip().lstrip("'"))
    if full is not None and len(tokens) == 1:
        return full

    # Комплект / складний код: шукаємо збіг будь-якої частини
    if len(tokens) > 1:
        # Якщо весь рядок починається з запиту («010 + 009K») —
        # це все одно комплект, ставимо нижче за чисті 010/010T
        if full is not None:
            best = 50 + full
        for idx, tok in enumerate(tokens):
            part = _token_relevance(query, tok)
            if part is None:
                continue
            score = 60 + part + idx
            best = score if best is None else min(best, score)
        return best

    return full


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
            data_rows = rows[1:] if rows else []
            # N: «Ссылка гугл фото» — часто smart chip / rich link, не звичайний HYPERLINK
            live_urls = _fetch_live_photo_urls(
                client, self.spreadsheet_id, ws.title, len(data_rows)
            )
            variants: list[ProductVariant] = []

            # A ID, B код, C назва, E колір, F наявність, G дроп-ціна, M фото, N живі фото
            for idx, row in enumerate(data_rows):
                while len(row) < 14:
                    row.append("")
                product_id = str(row[0]).strip()
                code = str(row[1]).strip().lstrip("'")
                name = str(row[2]).strip()
                color = str(row[4]).strip()
                if not code or not name:
                    continue
                live_photo_url = live_urls[idx] if idx < len(live_urls) else ""
                if not live_photo_url:
                    live_photo_url = _extract_url(str(row[13]).strip())
                variants.append(
                    ProductVariant(
                        product_id=product_id,
                        code=code,
                        name=name,
                        color=color,
                        stock=_parse_stock(row[5]),
                        drop_price=str(row[6]).strip(),
                        photo_url=str(row[12]).strip(),
                        live_photo_url=live_photo_url,
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
        - код: точний → префікс (010 → 010, 010T, 010TK) → токен у комплекті (010 + 009K)
        - назва: точна → починається з → містить; також код-токени в назві комплекту
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
                # Комплект інколи описаний у назві, а не лише в полі коду
                name_as_code = _code_relevance(query, v.name)
                if name_as_code is not None:
                    # Нижче за збіг у полі коду
                    name_as_code = 80 + name_as_code
                    code_score = (
                        name_as_code
                        if code_score is None
                        else min(code_score, name_as_code)
                    )
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
