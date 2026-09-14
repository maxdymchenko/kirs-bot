"""Повне видалення замовлень Mini App (SQLite + дзеркало в листі «Заказы»)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bot.accounts import AppStorage, Dropper, _now

logger = logging.getLogger(__name__)

VLAD_PRICE_JULY2026_ORDERS = (
    "K-260722-0002",
    "K-260722-0001",
    "K-260718-0001",
    "K-260719-0001",
)
VLAD_PRICE_PURGE_FLAG = "oneoff_purge_vlad_price_k2607"
_DROPPER_NEEDLES = ("влад прайс", "vlad price")


def _dropper_label(dropper: Dropper) -> str:
    title = str(dropper.owner_title or "").strip()
    company = str(dropper.company_name or "").strip()
    if title and company and title.casefold() != company.casefold():
        return f"{title} ({company})"
    return title or company or dropper.chat_id


def find_dropper_by_name(storage: AppStorage, name: str) -> Dropper | None:
    needle = " ".join(str(name or "").casefold().split())
    if not needle:
        return None
    hits: list[Dropper] = []
    for dropper in storage.list_droppers():
        blob = " ".join(
            str(x or "")
            for x in (dropper.owner_title, dropper.company_name, dropper.contact_name)
        ).casefold()
        blob = " ".join(blob.split())
        if needle in blob:
            hits.append(dropper)
            continue
        if all(part in blob for part in needle.split() if part):
            hits.append(dropper)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        logger.warning(
            "order purge: several droppers match %r: %s",
            name,
            [_dropper_label(d) for d in hits],
        )
        return None
    return None


def _unlink_local_pdfs(order: dict[str, Any]) -> None:
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    candidates: list[str] = []
    for key in ("ttn_pdf_local_abs", "ttn_pdf_local_path"):
        raw = str(payload.get(key) or "").strip()
        if raw:
            candidates.append(raw)
    for raw in candidates:
        path = Path(raw)
        if not path.is_absolute():
            continue
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            logger.warning("order purge: could not unlink PDF %s", path)


def _drop_sheet_warehouse_stage(storage: AppStorage, order_number: str) -> None:
    from bot.warehouse import SHEET_STAGE_KEY

    no = str(order_number or "").strip()
    if not no:
        return
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SHEET_STAGE_KEY,),
        ).fetchone()
        if not row:
            return
        try:
            data = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict) or no not in data:
            return
        data.pop(no, None)
        conn.execute(
            """
            UPDATE app_settings
            SET value_json = ?, updated_at = ?
            WHERE key = ?
            """,
            (json.dumps(data, ensure_ascii=False), _now(), SHEET_STAGE_KEY),
        )
        conn.commit()


def purge_dropper_orders(
    storage: AppStorage,
    *,
    dropper_name: str,
    order_numbers: list[str],
    dropper: Dropper | None = None,
) -> dict[str, Any]:
    wanted = [str(n or "").strip() for n in order_numbers if str(n or "").strip()]
    if dropper is None:
        dropper = find_dropper_by_name(storage, dropper_name)
    if not dropper:
        names = [_dropper_label(d) for d in storage.list_droppers() if d.status == "active"]
        return {
            "ok": False,
            "error": f"Дроппера «{dropper_name}» не знайдено",
            "active_droppers": names[:40],
            "purged": [],
            "skipped": wanted,
        }

    purged: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for number in wanted:
        order = storage.get_order_by_number(number)
        if not order:
            skipped.append({"order_number": number, "reason": "немає в базі"})
            _drop_sheet_warehouse_stage(storage, number)
            continue
        if int(order.get("dropper_id") or 0) != int(dropper.id):
            skipped.append(
                {
                    "order_number": number,
                    "reason": "замовлення іншого дроппера",
                }
            )
            continue
        _unlink_local_pdfs(order)
        oid = int(order["id"])
        storage.purge_order(oid)
        _drop_sheet_warehouse_stage(storage, number)
        purged.append({"id": oid, "order_number": number})

    sheet_numbers = [p["order_number"] for p in purged]
    sheet_numbers.extend(
        s["order_number"]
        for s in skipped
        if s.get("reason") == "немає в базі"
    )
    sheet_stats: dict[str, Any] = {"deleted_rows": 0, "error": ""}
    if sheet_numbers:
        try:
            from bot.orders_sheets import delete_sheet_rows_for_order_numbers

            sheet_stats = delete_sheet_rows_for_order_numbers(storage, sheet_numbers)
        except Exception as exc:
            logger.exception("order purge: sheet delete failed")
            sheet_stats = {"deleted_rows": 0, "error": str(exc)}

    return {
        "ok": True,
        "dropper": _dropper_label(dropper),
        "dropper_chat_id": dropper.chat_id,
        "purged": purged,
        "skipped": skipped,
        "sheet": sheet_stats,
    }


def _load_flag(storage: AppStorage, key: str) -> dict[str, Any] | None:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _save_flag(storage: AppStorage, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, body, _now()),
        )
        conn.commit()


def run_vlad_price_july2026_purge(storage: AppStorage) -> dict[str, Any]:
    """Одноразова чистка за запитом власника (Влад Прайс, липень 2026)."""
    prev = _load_flag(storage, VLAD_PRICE_PURGE_FLAG)
    if prev and prev.get("done"):
        return {"ok": True, "already_done": True, **prev}

    dropper = None
    for needle in _DROPPER_NEEDLES:
        dropper = find_dropper_by_name(storage, needle)
        if dropper:
            break
    if not dropper:
        names = [_dropper_label(d) for d in storage.list_droppers() if d.status == "active"]
        return {
            "ok": False,
            "error": "Дроппера «Влад Прайс» не знайдено",
            "active_droppers": names[:40],
            "purged": [],
            "skipped": list(VLAD_PRICE_JULY2026_ORDERS),
        }
    result = purge_dropper_orders(
        storage,
        dropper_name="Влад Прайс",
        order_numbers=list(VLAD_PRICE_JULY2026_ORDERS),
        dropper=dropper,
    )
    if not result.get("ok"):
        return result
    if (result.get("sheet") or {}).get("error"):
        return result
    flag = {
        "done": True,
        "at": _now(),
        "dropper": result.get("dropper"),
        "purged": result.get("purged"),
        "skipped": result.get("skipped"),
        "sheet": result.get("sheet"),
    }
    _save_flag(storage, VLAD_PRICE_PURGE_FLAG, flag)
    return {"ok": True, "already_done": False, **result}
