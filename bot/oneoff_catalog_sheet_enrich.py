"""Підтягнути складську назву/дроп у вже записані рядки маркетплейсів."""

from __future__ import annotations

import logging
from typing import Any

from bot.accounts import AppStorage
from bot.marketplace_ext import _lookup_item_catalog_meta, _trim
from bot.order_purge import _load_flag, _save_flag
from bot.orders_sheets import _norm_text, _open_orders_worksheet

logger = logging.getLogger(__name__)

FLAG = "oneoff_catalog_sheet_enrich_20260916"
_MARKET_MARKERS = (
    "rozetka",
    "розет",
    "prom",
    "пром",
    "kasta",
    "каста",
)


def run_catalog_sheet_enrich(storage: AppStorage, *, catalog: Any = None) -> dict[str, Any]:
    prev = _load_flag(storage, FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}
    if catalog is None:
        return {"ok": False, "error": "немає каталогу"}

    ws = _open_orders_worksheet(storage)
    values = ws.get_all_values()
    data: list[dict[str, Any]] = []
    changed: list[str] = []
    for i, row in enumerate(values[1:], start=2):
        while len(row) < 18:
            row.append("")
        source = _norm_text(row[10])
        if not any(marker in source for marker in _MARKET_MARKERS):
            continue
        code = _trim(row[5])
        if not code:
            continue
        loc, cat_name, _retail, drop, cat_color, _cat_code = _lookup_item_catalog_meta(
            catalog, code, _trim(row[6])
        )
        patches: dict[str, str] = {}
        if cat_name and _norm_text(cat_name) != _norm_text(row[4]):
            patches["E"] = cat_name
        if cat_color and not _trim(row[6]):
            patches["G"] = cat_color
        if drop and not _trim(row[9]):
            patches["J"] = drop
        if loc and not _trim(row[17]):
            patches["R"] = loc
        if not patches:
            continue
        for col, val in patches.items():
            data.append({"range": f"{col}{i}", "values": [[val]]})
        changed.append(f"{_trim(row[1]) or i}:{','.join(patches)}")

    if data:
        chunk = 80
        for start in range(0, len(data), chunk):
            ws.batch_update(
                data[start : start + chunk], value_input_option="USER_ENTERED"
            )

    result: dict[str, Any] = {
        "ok": True,
        "done": True,
        "changed": changed,
        "changed_count": len(changed),
    }
    _save_flag(storage, FLAG, result)
    logger.info("catalog sheet enrich: %s", result)
    return result
