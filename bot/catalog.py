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
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Роздільники в кодах комплектів: "010 + 009K", "010+009К", "010/009K"
_CODE_TOKEN_SPLIT_RE = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)
# Комплект лише за + або / (дефіс у коді на кшталт 1469Д-7080 — це не комплект)
_KIT_SEP_RE = re.compile(r"\s*[+/]\s*")
_KIT_MARK_RE = re.compile(r"[+/]")


class InsufficientStockError(Exception):
    """Недостатньо залишку для списання / оформлення замовлення."""


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
    sheet_row: int = 0  # 1-based рядок у Google Sheet (0 = невідомо)

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


def _is_kit_code(code: str) -> bool:
    return bool(_KIT_MARK_RE.search(str(code or "")))


def _kit_components(code: str) -> list[str]:
    """
    Складові комплекту.
    '405+625' → ['405', '625']
    '063+К' / '425+В' → ['063'] / ['425']  (літерний суфікс без цифр ігноруємо)
    '1469Д-7080' → [] (не комплект)
    """
    raw = str(code or "").strip().lstrip("'")
    if not raw or not _is_kit_code(raw):
        return []
    parts: list[str] = []
    for part in _KIT_SEP_RE.split(raw):
        token = part.strip().lstrip("'")
        if not token:
            continue
        # Суфікси на кшталт К / В — не окремий товар
        if not re.search(r"\d", token):
            continue
        parts.append(token)
    return parts


def _atomic_stock_by_code(variants: list[ProductVariant]) -> dict[str, int | None]:
    """
    Наявність «простих» товарів (не комплектів) за кодом.
    Сума по всіх рядках з цим кодом (різні кольори).
    None = у таблиці немає числа по цьому коду.
    """
    buckets: dict[str, list[int]] = {}
    for v in variants:
        if _is_kit_code(v.code):
            continue
        if v.stock is None:
            continue
        key = _code_raw(v.code)
        if not key:
            continue
        buckets.setdefault(key, []).append(int(v.stock))
    return {key: sum(vals) for key, vals in buckets.items()}


def _lookup_atomic_stock(
    stock_map: dict[str, int | None], code: str
) -> int | None:
    raw = _code_raw(code)
    if raw in stock_map:
        return stock_map[raw]
    # Fallback лише якщо точного коду немає (різний регістр / зайві пробіли вже в raw)
    norm = _normalize_code(code).casefold()
    if not norm:
        return None
    matches = [
        stock_map[k]
        for k in stock_map
        if _normalize_code(k).casefold() == norm
    ]
    if not matches:
        return None
    # Якщо кілька кодів зійшлись після зрізання нулів — беремо мінімум (безпечніше)
    return min(int(x) for x in matches)


def apply_component_stock_to_kits(
    variants: list[ProductVariant],
) -> tuple[list[ProductVariant], list[tuple[int, int]]]:
    """
    Якщо складова = 0 → комплект з цим кодом теж 0.
    Якщо складові знову в наявності → комплект = min(складових).
    Повертає (variants, [(sheet_row, new_stock), ...]) для запису в таблицю.
    """
    stock_map = _atomic_stock_by_code(variants)
    sheet_updates: list[tuple[int, int]] = []

    for v in variants:
        parts = _kit_components(v.code)
        if not parts:
            continue

        part_stocks: list[int] = []
        unknown = False
        forced_zero = False
        for part in parts:
            qty = _lookup_atomic_stock(stock_map, part)
            if qty is None:
                unknown = True
                continue
            if qty <= 0:
                forced_zero = True
                break
            part_stocks.append(qty)

        if forced_zero:
            new_stock = 0
        elif part_stocks and not unknown:
            new_stock = min(part_stocks)
        elif part_stocks and unknown:
            # Є відомі складові >0, але не всі — не чіпаємо, окрім випадку 0 вище
            continue
        else:
            continue

        if v.stock != new_stock:
            v.stock = new_stock
            if v.sheet_row > 0:
                sheet_updates.append((v.sheet_row, new_stock))

    return variants, sheet_updates


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

    @staticmethod
    def _write_stock_column(ws: gspread.Worksheet, updates: list[tuple[int, int]]) -> None:
        """Пакетний запис колонки F (наявність)."""
        if not updates:
            return
        by_row: dict[int, int] = {}
        for row_num, stock in updates:
            if row_num > 0:
                by_row[int(row_num)] = max(0, int(stock))
        if not by_row:
            return
        data = [
            {"range": f"F{row}", "values": [[stock]]}
            for row, stock in sorted(by_row.items())
        ]
        chunk = 80
        for i in range(0, len(data), chunk):
            ws.batch_update(data[i : i + chunk], value_input_option="USER_ENTERED")

    def _codes_equal(self, left: str, right: str) -> bool:
        a = _code_raw(left)
        b = _code_raw(right)
        if a and b and a == b:
            return True
        return _normalize_code(left).casefold() == _normalize_code(right).casefold()

    def _find_atomic_rows(
        self,
        variants: list[ProductVariant],
        code: str,
        *,
        color: str = "",
        product_id: str = "",
    ) -> list[ProductVariant]:
        rows = [v for v in variants if not _is_kit_code(v.code) and self._codes_equal(v.code, code)]
        if not rows:
            return []
        pid = str(product_id or "").strip()
        if pid:
            by_id = [v for v in rows if str(v.product_id or "").strip() == pid]
            if by_id:
                rows = by_id
        color_n = _norm_text(color)
        if color_n:
            by_color = [v for v in rows if color_n == _norm_text(v.color)]
            if by_color:
                return by_color
        return rows

    def _available_on_rows(self, rows: list[ProductVariant]) -> int | None:
        """Сума числових залишків; None якщо жоден рядок не трекає наявність."""
        vals = [int(v.stock) for v in rows if v.stock is not None]
        if not vals:
            return None
        return sum(vals)

    def _decrement_rows(
        self, rows: list[ProductVariant], qty: int
    ) -> list[tuple[int, int]]:
        """Списати qty з рядків із числовим stock. Повертає [(sheet_row, new_stock)]."""
        need = max(0, int(qty or 0))
        if need <= 0:
            return []
        tracked = [v for v in rows if v.stock is not None]
        if not tracked:
            return []
        available = sum(max(0, int(v.stock or 0)) for v in tracked)
        if available < need:
            raise InsufficientStockError(
                f"Недостатньо залишку (потрібно {need}, є {available})"
            )
        # Спочатку рядки з більшим залишком
        tracked.sort(key=lambda v: int(v.stock or 0), reverse=True)
        updates: list[tuple[int, int]] = []
        left = need
        for v in tracked:
            if left <= 0:
                break
            have = max(0, int(v.stock or 0))
            if have <= 0:
                continue
            take = min(have, left)
            new_stock = have - take
            v.stock = new_stock
            if v.sheet_row > 0:
                updates.append((v.sheet_row, new_stock))
            left -= take
        if left > 0:
            raise InsufficientStockError(
                f"Недостатньо залишку (не списано {left} шт.)"
            )
        return updates

    def _check_item_stock(
        self, variants: list[ProductVariant], item: dict
    ) -> None:
        code = str(item.get("code") or "").strip().lstrip("'")
        qty = max(1, int(item.get("qty") or 1))
        color = str(item.get("color") or "").strip()
        product_id = str(item.get("product_id") or "").strip()
        if not code:
            return

        if _is_kit_code(code):
            parts = _kit_components(code)
            if parts:
                for part in parts:
                    rows = self._find_atomic_rows(
                        variants, part, color=color, product_id=""
                    )
                    avail = self._available_on_rows(rows)
                    if avail is None:
                        continue
                    if avail < qty:
                        raise InsufficientStockError(
                            f"Немає в наявності складової {part} для комплекту {code} "
                            f"(потрібно {qty}, є {avail})"
                        )
                return
            # Комплект без розпізнаних складових — перевіряємо сам рядок
            rows = [
                v
                for v in variants
                if self._codes_equal(v.code, code)
                and (not color or _norm_text(v.color) == _norm_text(color))
            ]
            if product_id:
                by_id = [v for v in rows if str(v.product_id or "").strip() == product_id]
                if by_id:
                    rows = by_id
            avail = self._available_on_rows(rows)
            if avail is not None and avail < qty:
                raise InsufficientStockError(
                    f"Немає в наявності {code} (потрібно {qty}, є {avail})"
                )
            return

        rows = self._find_atomic_rows(
            variants, code, color=color, product_id=product_id
        )
        avail = self._available_on_rows(rows)
        if avail is not None and avail < qty:
            raise InsufficientStockError(
                f"Немає в наявності {code} (потрібно {qty}, є {avail})"
            )

    def _consume_item(
        self, variants: list[ProductVariant], item: dict
    ) -> list[tuple[int, int]]:
        code = str(item.get("code") or "").strip().lstrip("'")
        qty = max(1, int(item.get("qty") or 1))
        color = str(item.get("color") or "").strip()
        product_id = str(item.get("product_id") or "").strip()
        if not code:
            return []

        updates: list[tuple[int, int]] = []
        if _is_kit_code(code):
            parts = _kit_components(code)
            if parts:
                for part in parts:
                    rows = self._find_atomic_rows(
                        variants, part, color=color, product_id=""
                    )
                    # Якщо по кольору нічого з числовим stock — беремо будь-які атомарні
                    if not any(v.stock is not None for v in rows):
                        rows = self._find_atomic_rows(variants, part, color="", product_id="")
                    if any(v.stock is not None for v in rows):
                        updates.extend(self._decrement_rows(rows, qty))
                return updates

            rows = [
                v
                for v in variants
                if self._codes_equal(v.code, code)
                and (not color or _norm_text(v.color) == _norm_text(color))
            ]
            if product_id:
                by_id = [v for v in rows if str(v.product_id or "").strip() == product_id]
                if by_id:
                    rows = by_id
            if any(v.stock is not None for v in rows):
                updates.extend(self._decrement_rows(rows, qty))
            return updates

        rows = self._find_atomic_rows(
            variants, code, color=color, product_id=product_id
        )
        if any(v.stock is not None for v in rows):
            updates.extend(self._decrement_rows(rows, qty))
        return updates

    def _load_variants_from_sheet(
        self, ws: gspread.Worksheet, client: gspread.Client
    ) -> list[ProductVariant]:
        rows = ws.get_all_values()
        data_rows = rows[1:] if rows else []
        live_urls = _fetch_live_photo_urls(
            client, self.spreadsheet_id, ws.title, len(data_rows)
        )
        variants: list[ProductVariant] = []
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
                    sheet_row=idx + 2,
                )
            )
        return variants

    def _refresh_unlocked(self, *, sync_kits: bool = True) -> gspread.Worksheet | None:
        """Оновлення кешу без захоплення lock (викликати лише під self._lock)."""
        now = time.time()
        client = self._build_client()
        ws = client.open_by_key(self.spreadsheet_id).sheet1
        variants = self._load_variants_from_sheet(ws, client)
        kit_updates: list[tuple[int, int]] = []
        if sync_kits:
            variants, kit_updates = apply_component_stock_to_kits(variants)
            if kit_updates:
                try:
                    self._write_stock_column(ws, kit_updates)
                    logger.info(
                        "Наявність комплектів синхронізовано в таблицю: %d рядків",
                        len(kit_updates),
                    )
                except Exception:
                    logger.exception(
                        "Не вдалося записати наявність комплектів у Google Sheet "
                        "(у застосунку вже застосовано)"
                    )
        self._variants = variants
        self._loaded_at = now
        logger.info("Каталог загружен: %d позиций", len(variants))
        return ws

    def refresh(self, force: bool = False) -> None:
        with self._lock:
            now = time.time()
            if not force and self._variants and now - self._loaded_at < self.cache_ttl_seconds:
                return
            self._refresh_unlocked(sync_kits=True)

    def consume_cart_stock(self, cart: list[dict]) -> dict:
        """
        Списати залишки після продажу.
        Комплект → мінус по кожній складовій, потім перерахунок комплектів.
        Звичайний товар → мінус по його рядку + перерахунок комплектів.
        """
        items = [x for x in (cart or []) if isinstance(x, dict)]
        if not items:
            return {"ok": True, "updated_rows": 0, "items": 0}

        with self._lock:
            client = self._build_client()
            ws = client.open_by_key(self.spreadsheet_id).sheet1
            variants = self._load_variants_from_sheet(ws, client)

            # Перевірка до списання
            for item in items:
                self._check_item_stock(variants, item)

            sheet_updates: list[tuple[int, int]] = []
            for item in items:
                sheet_updates.extend(self._consume_item(variants, item))

            variants, kit_updates = apply_component_stock_to_kits(variants)
            sheet_updates.extend(kit_updates)

            if sheet_updates:
                self._write_stock_column(ws, sheet_updates)

            self._variants = variants
            self._loaded_at = time.time()
            logger.info(
                "Списання наявності: items=%d sheet_rows=%d",
                len(items),
                len({r for r, _ in sheet_updates}),
            )
            return {
                "ok": True,
                "updated_rows": len({r for r, _ in sheet_updates}),
                "items": len(items),
            }

    def _restore_item(
        self, variants: list[ProductVariant], item: dict
    ) -> list[tuple[int, int]]:
        """Повернути qty на склад (дзеркало _consume_item)."""
        code = str(item.get("code") or "").strip().lstrip("'")
        qty = max(1, int(item.get("qty") or 1))
        color = str(item.get("color") or "").strip()
        product_id = str(item.get("product_id") or "").strip()
        if not code:
            return []

        updates: list[tuple[int, int]] = []
        if _is_kit_code(code):
            parts = _kit_components(code)
            if parts:
                for part in parts:
                    rows = self._find_atomic_rows(
                        variants, part, color=color, product_id=""
                    )
                    if not any(v.stock is not None for v in rows):
                        rows = self._find_atomic_rows(variants, part, color="", product_id="")
                    if any(v.stock is not None for v in rows):
                        updates.extend(self._increment_rows(rows, qty))
                return updates

            rows = [
                v
                for v in variants
                if self._codes_equal(v.code, code)
                and (not color or _norm_text(v.color) == _norm_text(color))
            ]
            if product_id:
                by_id = [v for v in rows if str(v.product_id or "").strip() == product_id]
                if by_id:
                    rows = by_id
            if any(v.stock is not None for v in rows):
                updates.extend(self._increment_rows(rows, qty))
            return updates

        rows = self._find_atomic_rows(
            variants, code, color=color, product_id=product_id
        )
        if any(v.stock is not None for v in rows):
            updates.extend(self._increment_rows(rows, qty))
        return updates

    def _increment_rows(
        self, rows: list[ProductVariant], qty: int
    ) -> list[tuple[int, int]]:
        need = max(0, int(qty or 0))
        if need <= 0:
            return []
        tracked = [v for v in rows if v.stock is not None]
        if not tracked:
            return []
        # Повертаємо на рядок з найбільшим sheet_row / перший tracked
        tracked.sort(key=lambda v: int(v.sheet_row or 0), reverse=True)
        target = tracked[0]
        new_stock = max(0, int(target.stock or 0)) + need
        target.stock = new_stock
        if target.sheet_row > 0:
            return [(target.sheet_row, new_stock)]
        return []

    def restore_cart_stock(self, cart: list[dict]) -> dict:
        """Повернути залишки після скасування/редагування замовлення."""
        items = [x for x in (cart or []) if isinstance(x, dict)]
        if not items:
            return {"ok": True, "updated_rows": 0, "items": 0}

        with self._lock:
            client = self._build_client()
            ws = client.open_by_key(self.spreadsheet_id).sheet1
            variants = self._load_variants_from_sheet(ws, client)

            sheet_updates: list[tuple[int, int]] = []
            for item in items:
                sheet_updates.extend(self._restore_item(variants, item))

            variants, kit_updates = apply_component_stock_to_kits(variants)
            sheet_updates.extend(kit_updates)

            if sheet_updates:
                self._write_stock_column(ws, sheet_updates)

            self._variants = variants
            self._loaded_at = time.time()
            logger.info(
                "Повернення наявності: items=%d sheet_rows=%d",
                len(items),
                len({r for r, _ in sheet_updates}),
            )
            return {
                "ok": True,
                "updated_rows": len({r for r, _ in sheet_updates}),
                "items": len(items),
            }

    def replace_cart_stock(self, old_cart: list[dict], new_cart: list[dict]) -> dict:
        """Спочатку повернути старий кошик, потім списати новий."""
        self.restore_cart_stock(old_cart or [])
        return self.consume_cart_stock(new_cart or [])

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
