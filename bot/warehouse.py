"""Черга пакування / відправлення для комірника (warehouse)."""

from __future__ import annotations

import io
import logging
from typing import Any

from bot.accounts import AppStorage
from bot.np_fulfillment import AWAITING_SHIPMENT_STATUSES, SHIPPED_OR_FINAL_STATUSES

logger = logging.getLogger(__name__)

STAGE_PACKING = "packing"
STAGE_READY = "ready_to_ship"

# Власна ТТН дроппера теж пакується на складі, поки НП ще не забрала.
PACKABLE_TTN_STATUSES = frozenset(AWAITING_SHIPMENT_STATUSES | {"provided"})


def order_warehouse_stage(order: dict[str, Any]) -> str:
    raw = str(order.get("warehouse_stage") or "").strip()
    if raw in {STAGE_PACKING, STAGE_READY}:
        return raw
    payload = order.get("payload") or {}
    raw2 = str(payload.get("warehouse_stage") or "").strip()
    if raw2 in {STAGE_PACKING, STAGE_READY}:
        return raw2
    return STAGE_PACKING


def is_packable_order(order: dict[str, Any]) -> bool:
    if str(order.get("status") or "") == "cancelled":
        return False
    if str(order.get("sheets_sync_status") or "") == "hold_pdf":
        return False
    payload = order.get("payload") or {}
    if payload.get("ttn_pdf_hold") is True:
        return False
    ttn = str(order.get("ttn_status") or "none").strip() or "none"
    if ttn in SHIPPED_OR_FINAL_STATUSES:
        return False
    if ttn not in PACKABLE_TTN_STATUSES:
        return False
    return True


def list_warehouse_queue(
    storage: AppStorage,
    *,
    stage: str,
    limit: int = 300,
) -> list[dict[str, Any]]:
    stage_key = STAGE_READY if stage == STAGE_READY else STAGE_PACKING
    items = storage.list_orders_for_warehouse(limit=limit)
    out: list[dict[str, Any]] = []
    for order in items:
        if not is_packable_order(order):
            continue
        if order_warehouse_stage(order) != stage_key:
            continue
        out.append(order)
    # новіші зверху (created_at DESC уже з SQL, але підстрахуємо)
    out.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return out


def mark_order_ready_to_ship(
    storage: AppStorage,
    order_id: int,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    order = storage.get_order(int(order_id))
    if not order:
        raise ValueError("Замовлення не знайдено")
    if not is_packable_order(order):
        raise ValueError("Замовлення вже не в черзі на пакування")
    if order_warehouse_stage(order) == STAGE_READY:
        return order
    storage.set_order_warehouse_stage(int(order_id), STAGE_READY)
    storage.merge_order_payload(
        int(order_id),
        {
            "warehouse_stage": STAGE_READY,
            "warehouse_ready_by": str(actor_user_id or ""),
        },
    )
    storage.add_order_change(
        order_id=int(order_id),
        order_number=str(order.get("order_number") or ""),
        actor_role="warehouse",
        actor_user_id=str(actor_user_id or ""),
        actor_label="Комірник",
        change_type="status",
        summary="Переміщено на відправлення (упаковано)",
        diff=[
            {
                "field": "warehouse_stage",
                "old": STAGE_PACKING,
                "new": STAGE_READY,
            }
        ],
    )
    return storage.get_order(int(order_id)) or order


def mark_order_back_to_packing(
    storage: AppStorage,
    order_id: int,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    order = storage.get_order(int(order_id))
    if not order:
        raise ValueError("Замовлення не знайдено")
    storage.set_order_warehouse_stage(int(order_id), STAGE_PACKING)
    storage.merge_order_payload(
        int(order_id),
        {"warehouse_stage": STAGE_PACKING},
    )
    storage.add_order_change(
        order_id=int(order_id),
        order_number=str(order.get("order_number") or ""),
        actor_role="warehouse",
        actor_user_id=str(actor_user_id or ""),
        actor_label="Комірник",
        change_type="status",
        summary="Повернено на пакування",
        diff=[
            {
                "field": "warehouse_stage",
                "old": STAGE_READY,
                "new": STAGE_PACKING,
            }
        ],
    )
    return storage.get_order(int(order_id)) or order


def order_has_ttn_pdf(order: dict[str, Any]) -> bool:
    payload = order.get("payload") or {}
    return bool(
        payload.get("ttn_pdf_local_path")
        or payload.get("ttn_pdf_local_abs")
        or payload.get("ttn_pdf_drive_file_id")
    )


def ensure_order_ttn_pdf(storage: AppStorage, order: dict[str, Any]) -> dict[str, Any]:
    """
    Якщо локального PDF немає — спробувати завантажити етикетку з НП
    (для замовлень, створених ключем власника).
    """
    from bot.ttn_drive import persist_order_ttn_pdf
    from bot.ttn_store import read_pdf_bytes

    payload = order.get("payload") or {}
    local = str(
        payload.get("ttn_pdf_local_path") or payload.get("ttn_pdf_local_abs") or ""
    ).strip()
    if local:
        try:
            read_pdf_bytes(local)
            return order
        except Exception:
            logger.info(
                "TTN local PDF missing for %s — try NP re-download",
                order.get("order_number"),
            )

    if payload.get("ttn_pdf_drive_file_id"):
        return order

    if order.get("own_ttn"):
        raise ValueError(
            f"{order.get('order_number')}: власна ТТН без завантаженого PDF"
        )

    doc_ref = str(payload.get("np_document_ref") or "").strip()
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    if not doc_ref and not ttn:
        raise ValueError(f"{order.get('order_number')}: немає Ref/ТТН для друку")

    from bot.np_fulfillment import list_np_clients
    from bot.novaposhta import NovaPoshtaError

    clients = list_np_clients(storage)
    if not clients:
        raise ValueError("Немає API-ключа Нової Пошти для друку етикетки")

    last_err: Exception | None = None
    pdf_bytes: bytes | None = None
    for label, client, _is_primary in clients:
        try:
            # Спочатку Ref документа; якщо немає — НП print інколи приймає номер у URL
            key = doc_ref or ttn
            pdf_bytes = client.download_marking_pdf(key)
            break
        except Exception as exc:
            last_err = exc
            logger.warning(
                "NP label download via «%s» failed order=%s: %s",
                label,
                order.get("order_number"),
                exc,
            )
    if not pdf_bytes:
        raise ValueError(
            f"{order.get('order_number')}: не вдалося завантажити PDF з НП"
            + (f" ({last_err})" if last_err else "")
        ) from last_err

    saved = persist_order_ttn_pdf(
        storage,
        order,
        pdf_bytes=pdf_bytes,
        source="np_print_backfill",
        filename=f"{order.get('order_number')}_{ttn or 'label'}.pdf",
    )
    return saved or storage.get_order(int(order["id"])) or order


def merge_ready_ttn_pdfs(storage: AppStorage, orders: list[dict[str, Any]]) -> bytes:
    """Злити PDF накладних: 1 файл = 1+ листів, кожна накладна з нової сторінки."""
    from pypdf import PdfReader, PdfWriter

    from bot.ttn_drive import download_pdf_bytes
    from bot.ttn_store import read_pdf_bytes

    writer = PdfWriter()
    used = 0
    errors: list[str] = []
    for order in orders:
        try:
            order = ensure_order_ttn_pdf(storage, order)
        except Exception as exc:
            errors.append(str(exc))
            continue
        payload = order.get("payload") or {}
        local = str(
            payload.get("ttn_pdf_local_path")
            or payload.get("ttn_pdf_local_abs")
            or ""
        ).strip()
        file_id = str(payload.get("ttn_pdf_drive_file_id") or "").strip()
        try:
            if local:
                raw = read_pdf_bytes(local)
            elif file_id:
                raw = download_pdf_bytes(file_id)
            else:
                errors.append(str(order.get("order_number") or order.get("id")))
                continue
            reader = PdfReader(io.BytesIO(raw))
            for page in reader.pages:
                writer.add_page(page)
            used += 1
        except Exception as exc:
            logger.exception(
                "merge pdf failed order=%s", order.get("order_number")
            )
            errors.append(f"{order.get('order_number')}: {exc}")
    if used == 0:
        raise ValueError(
            "Немає PDF накладних для злиття. "
            + (", ".join(errors[:5]) if errors else "Завантажте/створіть ТТН ще раз.")
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
