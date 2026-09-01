"""Модуль щогодинної синхронізації залишків та цін з Prom.ua (Пром Кірс).

Перевіряє зміни в стовпцях A (ID товару Prom), F (залишок), G (дроп-ціна), H (роздрібна ціна)
і пакетами до 100 товарів відправляє оновлення через POST https://my.prom.ua/api/v1/products/edit.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from bot.accounts import AppStorage
from bot.catalog import CatalogService, ProductVariant

logger = logging.getLogger(__name__)

PROM_API_BASE = "https://my.prom.ua/api/v1"
SETTINGS_STATE_KEY = "prom_sync_state"


def _parse_price(raw: Any) -> float | None:
    """Очищення та парсинг ціни (наприклад '1 100,00 грн' -> 1100.0)."""
    if raw is None:
        return None
    s = str(raw).strip().replace("\u00a0", " ")
    if not s:
        return None
    # Витягуємо числову частину (підтримує пробіли між тисячами та кому як розділювач)
    m = re.search(r"(\d[\d\s]*([,\.]\d{1,2})?)", s)
    if not m:
        return None
    num_str = m.group(1).replace(" ", "").replace(",", ".")
    try:
        val = float(num_str)
        return round(val, 2) if val >= 0 else None
    except (TypeError, ValueError):
        return None


def _is_valid_prom_id(product_id: Any) -> bool:
    """Перевіряє, чи є ID коректним числовим ідентифікатором товару на Prom.ua."""
    s = str(product_id or "").strip()
    return bool(s.isdigit() and int(s) > 0)


def send_prom_products_edit(
    token: str, products_payload: list[dict[str, Any]]
) -> dict[str, Any]:
    """Відправка пакетного оновлення товарів до Prom.ua API.

    POST https://my.prom.ua/api/v1/products/edit
    """
    if not token or not products_payload:
        return {"ok": False, "error": "Порожній токен або дані"}

    url = f"{PROM_API_BASE}/products/edit"
    body = json.dumps(products_payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "KirsBot/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            data_raw = resp.read().decode("utf-8")
            try:
                res_json = json.loads(data_raw)
            except Exception:
                res_json = {"raw": data_raw}
            return {"ok": True, "status": resp.status, "data": res_json}
    except HTTPError as err:
        err_body = ""
        try:
            err_body = err.read().decode("utf-8")
        except Exception:
            pass
        logger.error("Prom.ua API edit HTTP error %s: %s", err.code, err_body)
        return {"ok": False, "error": f"HTTP {err.code}: {err_body}"}
    except URLError as err:
        logger.error("Prom.ua API edit URL error: %s", err.reason)
        return {"ok": False, "error": str(err.reason)}
    except Exception as exc:
        logger.exception("Prom.ua API edit unexpected error: %s", exc)
        return {"ok": False, "error": str(exc)}


def load_prom_sync_snapshot(storage: AppStorage) -> dict[str, dict[str, Any]]:
    """Отримати попередній збережений знімок стану товарів Prom."""
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_STATE_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_prom_sync_snapshot(
    storage: AppStorage, snapshot: dict[str, dict[str, Any]]
) -> None:
    """Зберегти поточний знімок стану товарів Prom."""
    now_iso = time.strftime("%Y-%m-%d %H:%M:%S")
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SETTINGS_STATE_KEY, json.dumps(snapshot, ensure_ascii=False), now_iso),
        )
        conn.commit()


def run_prom_sync_pass(
    storage: AppStorage,
    catalog: CatalogService,
    *,
    force_all: bool = False,
) -> dict[str, Any]:
    """Основний прохід синхронізації з Prom.ua.

    Визначає товари, у яких за останній прохід змінився залишок або ціни,
    і відправляє оновлення до Prom.ua пакетами по 100 товарів.
    """
    settings = storage.get_general_settings()
    token = str(
        settings.get("prom_api_token")
        or os.getenv("PROM_KIRS_TOKEN")
        or ""
    ).strip()

    sync_stock = bool(settings.get("prom_sync_stock"))
    sync_retail = bool(settings.get("prom_sync_retail_price"))
    sync_drop = bool(settings.get("prom_sync_drop_price"))

    if not token:
        return {"ok": True, "skipped": True, "reason": "Prom API token не налаштовано"}

    if not (sync_stock or sync_retail or sync_drop):
        return {
            "ok": True,
            "skipped": True,
            "reason": "Всі чекбокси синхронізації з Prom вимкнено",
        }

    # Оновлюємо дані каталогу з таблиці наявності
    try:
        catalog.refresh(force=True)
    except Exception:
        logger.exception("Failed to refresh catalog for Prom sync")

    variants = catalog.all_variants()
    if not variants:
        return {"ok": True, "skipped": True, "reason": "Каталог порожній"}

    # Збираємо актуальний стан товарів з валідними Product ID (Стовпець A)
    # Якщо один product_id зустрічається в кількох рядках — беремо перший або зведений
    current_snapshot: dict[str, dict[str, Any]] = {}
    for v in variants:
        pid = str(v.product_id or "").strip()
        if not _is_valid_prom_id(pid):
            continue

        stock_val = max(0, int(v.stock)) if v.stock is not None else 0
        retail_val = _parse_price(v.retail_price)
        drop_val = _parse_price(v.drop_price)

        if pid not in current_snapshot:
            current_snapshot[pid] = {
                "stock": stock_val,
                "retail": retail_val,
                "drop": drop_val,
            }
        else:
            # Якщо є дублі рядків з тим самим product_id — актуалізуємо
            current_snapshot[pid]["stock"] = max(
                current_snapshot[pid]["stock"], stock_val
            )
            if retail_val is not None:
                current_snapshot[pid]["retail"] = retail_val
            if drop_val is not None:
                current_snapshot[pid]["drop"] = drop_val

    prev_snapshot = load_prom_sync_snapshot(storage)

    # Визначаємо змінені товари
    to_update: list[dict[str, Any]] = []

    for pid, cur in current_snapshot.items():
        prev = prev_snapshot.get(pid)
        is_changed = False

        if force_all or prev is None:
            is_changed = True
        else:
            if sync_stock and cur.get("stock") != prev.get("stock"):
                is_changed = True
            if sync_retail and cur.get("retail") != prev.get("retail"):
                is_changed = True
            if sync_drop and cur.get("drop") != prev.get("drop"):
                is_changed = True

        if not is_changed:
            continue

        item_payload: dict[str, Any] = {"id": int(pid)}

        if sync_stock:
            stock = cur["stock"]
            item_payload["presence"] = "available" if stock > 0 else "not_available"
            item_payload["quantity_in_stock"] = stock

        if sync_retail and cur["retail"] is not None:
            item_payload["price"] = cur["retail"]

        if sync_drop and cur["drop"] is not None:
            min_qty = int(settings.get("prom_wholesale_min_qty") or 5)
            item_payload["prices"] = [
                {"price": cur["drop"], "minimum_order_quantity": max(1, min_qty)}
            ]

        to_update.append(item_payload)

    if not to_update:
        save_prom_sync_snapshot(storage, current_snapshot)
        return {
            "ok": True,
            "total_prom_items": len(current_snapshot),
            "updated_items": 0,
            "message": "Змін залишків та цін для Prom.ua не виявлено",
        }

    logger.info(
        "Prom.ua sync: виявлено %d змінених товарів, відправка до API...",
        len(to_update),
    )

    # Відправка пакетами до 100 товарів
    chunk_size = 100
    success_count = 0
    errors: list[str] = []

    for i in range(0, len(to_update), chunk_size):
        chunk = to_update[i : i + chunk_size]
        res = send_prom_products_edit(token, chunk)
        if res.get("ok"):
            success_count += len(chunk)
        else:
            err = str(res.get("error") or "Помилка")
            errors.append(f"Чанк {i // chunk_size + 1}: {err}")
            logger.error("Prom.ua sync chunk failed: %s", err)
        time.sleep(0.3)

    # Зберігаємо актуальний стан
    save_prom_sync_snapshot(storage, current_snapshot)

    logger.info(
        "Prom.ua sync завершено: оновлено %d/%d товарів",
        success_count,
        len(to_update),
    )

    return {
        "ok": len(errors) == 0,
        "total_prom_items": len(current_snapshot),
        "changed_items": len(to_update),
        "updated_items": success_count,
        "errors": errors,
    }
