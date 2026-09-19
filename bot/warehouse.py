"""Черга пакування / відправлення для комірника (warehouse)."""

from __future__ import annotations

import io
import json
import logging
import re
import time
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.np_fulfillment import AWAITING_SHIPMENT_STATUSES, SHIPPED_OR_FINAL_STATUSES

logger = logging.getLogger(__name__)
KYIV = ZoneInfo("Europe/Kyiv")

STAGE_PACKING = "packing"
STAGE_READY = "ready_to_ship"
STAGE_SHIPPED = "shipped"
STAGE_NEXT = "next_ship"
WAREHOUSE_STAGES = frozenset(
    {STAGE_PACKING, STAGE_READY, STAGE_SHIPPED, STAGE_NEXT}
)
NEXT_SHIP_PROMOTE_HOUR = 21
NEXT_SHIP_PROMOTE_KEY = "next_ship_promote_state"
# 14:00 ще сьогодні, 14:01 вже черга; субота — 13:00 / 13:01; неділя без порогу.
_WEEKDAY_CUTOFF = {
    0: time(14, 1),  # пн
    1: time(14, 1),
    2: time(14, 1),
    3: time(14, 1),
    4: time(14, 1),
    5: time(13, 1),  # сб
}
SHEET_ID_PREFIX = "sheet:"
SHEET_STAGE_KEY = "sheet_warehouse_stages"
SHEET_ENTERED_KEY = "sheet_packing_entered_at"
# Пром/Rozetka/ручні з листа: старше цього не показуємо в чергах комірника.
SHEET_WAREHOUSE_MAX_AGE_DAYS = 7

# Власна ТТН дроппера теж пакується на складі, поки НП ще не забрала.
PACKABLE_TTN_STATUSES = frozenset(AWAITING_SHIPMENT_STATUSES | {"provided"})

_MARKET_SOURCE_MARKERS = (
    "пром",
    "prom",
    "rozetka",
    "розет",
    "kasta",
    "каста",
    "телефон",
    "olx",
    "instagram",
    "інстаграм",
    "инстаграм",
    "інше",
    "viber",
)
_LEFT_WAREHOUSE_STATUS = (
    "в дорозі",
    "у дорозі",
    "в дороге",
    "на відділен",
    "на отделен",
    "у відділен",
    "прибув на",
    "прибыл на",
    "передано перевізнику",
    "передано кур",
    "видано кур",
    "прямує до",
    "у місті",
    "в городе",
    "на шляху",
    "на пути",
    "відправлення прийнято",
    "отправление принято",
    "доставляється",
    "передано до служби",
    "очікує в пункті",
    "видано одержувачу",
    "відправлено",
    "отправлено",
)
_NP_LIVE_CACHE_TTL_SEC = 300.0
_np_live_cache_at = 0.0
_np_live_cache_key: frozenset[str] = frozenset()
_np_live_cache_data: dict[str, dict[str, Any]] = {}
_ROZETKA_LIVE_CACHE_TTL_SEC = 300.0
_rozetka_live_cache_at = 0.0
_rozetka_live_cache_key: frozenset[str] = frozenset()
_rozetka_live_cache_data: dict[str, str] = {}


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def initial_warehouse_stage(now: datetime | None = None) -> str:
    """Куди класти щойно прийняте замовлення: пакування чи «Наступна відправка»."""
    dt = now_kyiv(now)
    if dt.weekday() == 6:
        return STAGE_PACKING
    clock = dt.timetz().replace(tzinfo=None)
    if clock >= time(NEXT_SHIP_PROMOTE_HOUR, 0):
        return STAGE_PACKING
    cutoff = _WEEKDAY_CUTOFF.get(dt.weekday())
    if cutoff and clock >= cutoff:
        return STAGE_NEXT
    return STAGE_PACKING


def normalize_warehouse_stage(stage: str | None) -> str:
    raw = str(stage or "").strip()
    if raw in WAREHOUSE_STAGES:
        return raw
    return STAGE_PACKING


def order_warehouse_stage(order: dict[str, Any]) -> str:
    raw = str(order.get("warehouse_stage") or "").strip()
    if raw in WAREHOUSE_STAGES:
        return raw
    payload = order.get("payload") or {}
    raw2 = str(payload.get("warehouse_stage") or "").strip()
    if raw2 in WAREHOUSE_STAGES:
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
    if payload.get("warehouse_left_manually") or payload.get("warehouse_left_via_tracking"):
        return False
    if order_warehouse_stage(order) == STAGE_SHIPPED:
        return False
    ttn = str(order.get("ttn_status") or "none").strip() or "none"
    if ttn in SHIPPED_OR_FINAL_STATUSES:
        return False
    if ttn not in PACKABLE_TTN_STATUSES:
        return False
    return True


def is_sheet_queue_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    if payload.get("sheet_order"):
        return True
    return str(order.get("id") or "").startswith(SHEET_ID_PREFIX)


def sheet_order_id(order_no: str) -> str:
    return f"{SHEET_ID_PREFIX}{str(order_no or '').strip()}"


def parse_sheet_order_id(order_id: Any) -> str | None:
    raw = str(order_id or "").strip()
    if raw.startswith(SHEET_ID_PREFIX):
        no = raw[len(SHEET_ID_PREFIX) :].strip()
        return no or None
    return None


def _clean_location(raw: Any) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    folded = text.casefold()
    if folded in {"-", "—", "–", "н/д", "нет", "немає", "null", "none"}:
        return ""
    if folded.startswith("уточнен"):
        return ""
    return text


def _is_market_or_manual_source(source: str, order_no: str = "") -> bool:
    text = str(source or "").casefold()
    no = str(order_no or "").strip().upper()
    if no.startswith("TEL-"):
        return True
    if not text:
        return False
    return any(marker in text for marker in _MARKET_SOURCE_MARKERS)


def _is_sheet_row_still_packing(status: str) -> bool:
    from bot.sheet_tracking import is_terminal_sheet_status

    raw = str(status or "").strip()
    if is_terminal_sheet_status(raw):
        return False
    folded = raw.casefold()
    return not any(word in folded for word in _LEFT_WAREHOUSE_STATUS)


def _sheet_qty(raw: Any) -> int:
    text = str(raw or "").strip().replace(" ", "").replace(",", ".")
    try:
        n = int(float(text)) if text else 1
    except (TypeError, ValueError):
        n = 1
    return max(1, n)


def _sheet_created_at(raw: Any, row_idx: int) -> str:
    text = str(raw or "").strip()
    for fmt, size in (
        ("%d.%m.%Y %H:%M:%S", 19),
        ("%d.%m.%Y %H:%M", 16),
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%d.%m.%Y", 10),
        ("%Y-%m-%d", 10),
    ):
        chunk = text[:size]
        try:
            return datetime.strptime(chunk, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return f"1970-01-01 {max(0, int(row_idx)):08d}"


def _parse_created_dt(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    iso = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KYIV)
        return dt
    except ValueError:
        pass
    for fmt, size in (
        ("%d.%m.%Y %H:%M:%S", 19),
        ("%d.%m.%Y %H:%M", 16),
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%d.%m.%Y", 10),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(text[:size], fmt).replace(tzinfo=KYIV)
        except ValueError:
            continue
    return None


def created_at_sort_value(created_at: Any) -> float:
    dt = _parse_created_dt(created_at)
    if dt is None:
        return 0.0
    return dt.timestamp()


def format_warehouse_entered_label(created_at: Any) -> str:
    """Підпис для картки комірника: «внесено 14.09.26 о 12:01»."""
    dt = _parse_created_dt(created_at)
    if dt is None:
        return ""
    local = dt.astimezone(KYIV)
    date = local.strftime("%d.%m.%y")
    text = str(created_at or "").strip()
    date_only = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2} 00:00:00", text))
    if date_only:
        return f"внесено {date}"
    return f"внесено {date} о {local.strftime('%H:%M')}"


def _queue_sort_key(order: dict[str, Any]) -> tuple[float, float]:
    extra = 0.0
    try:
        extra = float(order.get("id") or 0)
    except (TypeError, ValueError):
        extra = float(order.get("sheet_row") or 0)
    return (created_at_sort_value(order.get("created_at")), extra)


def is_sheet_order_stale_for_warehouse(order: dict[str, Any]) -> bool:
    """Старі рядки листа (як 338739909 з квітня) не тримаємо в пакуванні / відправленні."""
    if not is_sheet_queue_order(order):
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    raw = str(payload.get("sheet_created_at") or order.get("created_at") or "").strip()
    dt = _parse_created_dt(raw)
    if dt is None:
        return False
    now = now_kyiv()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV)
    else:
        dt = dt.astimezone(KYIV)
    return (now - dt).days >= SHEET_WAREHOUSE_MAX_AGE_DAYS


def _looks_like_np_ttn(ttn: str) -> bool:
    digits = "".join(ch for ch in str(ttn or "") if ch.isdigit())
    return len(digits) >= 11


def warehouse_delivery_carrier(order: dict[str, Any]) -> str:
    """Служба доставки для фільтра: np | rozetka | ukrposhta."""
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    if ttn.upper().startswith("RMP-"):
        return "rozetka"
    own = str(payload.get("own_ttn_carrier") or "").strip().lower().replace("-", "_")
    if own in {"rozetka", "rz", "rmp"}:
        return "rozetka"
    if "ukr" in own or "укрпошт" in own:
        return "ukrposhta"
    if own in {"nova_poshta", "novaposhta", "np", "нп"}:
        return "np"
    delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    bits = " ".join(
        str(x or "")
        for x in (
            payload.get("carrier"),
            payload.get("delivery_carrier"),
            delivery.get("carrier"),
            delivery.get("method"),
            order.get("delivery_method"),
        )
    ).casefold()
    if "укрпошт" in bits or "ukrposht" in bits:
        return "ukrposhta"
    if "розет" in bits or "rozetka" in bits or "rmp" in bits:
        return "rozetka"
    if "нов" in bits and ("пошт" in bits or "почт" in bits):
        return "np"
    if bits in {"нп", "np"} or "nova_poshta" in bits or "novaposhta" in bits:
        return "np"
    digits = "".join(ch for ch in ttn if ch.isdigit())
    if digits.startswith(("204", "205", "206", "207", "208", "590", "591")) and 13 <= len(digits) <= 14:
        return "np"
    if _looks_like_np_ttn(ttn):
        return "np"
    return "np"


def warehouse_delivery_carrier_label(code: str) -> str:
    return {
        "rozetka": "Розетка",
        "ukrposhta": "Укрпошта",
        "np": "Нова Пошта",
    }.get(str(code or "").strip(), "Нова Пошта")


def _load_sheet_stages(storage: AppStorage) -> dict[str, str]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SHEET_STAGE_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in data.items():
        no = str(key or "").strip()
        stage = str(val or "").strip()
        if no and stage in WAREHOUSE_STAGES:
            out[no] = stage
    return out


def _save_sheet_stages(storage: AppStorage, stages: dict[str, str]) -> None:
    from bot.accounts import _now

    cleaned = {
        str(k).strip(): str(v)
        for k, v in (stages or {}).items()
        if str(k).strip() and str(v) in WAREHOUSE_STAGES
    }
    payload = json.dumps(cleaned, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SHEET_STAGE_KEY, payload, _now()),
        )
        conn.commit()


def set_sheet_warehouse_stage(
    storage: AppStorage, order_no: str, stage: str
) -> None:
    no = str(order_no or "").strip()
    stage_key = normalize_warehouse_stage(stage)
    if not no:
        raise ValueError("Немає номера замовлення")
    stages = _load_sheet_stages(storage)
    stages[no] = stage_key
    _save_sheet_stages(storage, stages)


def _load_sheet_entered_at(storage: AppStorage) -> dict[str, str]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SHEET_ENTERED_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in data.items():
        no = str(key or "").strip()
        when = str(val or "").strip()
        if no and when:
            out[no] = when
    return out


def _save_sheet_entered_at(storage: AppStorage, stamps: dict[str, str]) -> None:
    from bot.accounts import _now

    cleaned = {
        str(k).strip(): str(v).strip()
        for k, v in (stamps or {}).items()
        if str(k).strip() and str(v).strip()
    }
    payload = json.dumps(cleaned, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SHEET_ENTERED_KEY, payload, _now()),
        )
        conn.commit()


def remember_sheet_entered_at(
    storage: AppStorage, order_numbers: list[str] | tuple[str, ...]
) -> None:
    """Запам'ятати час першого запису в таблицю «Заказы» (вкладка «На пакування»)."""
    nos = [str(n or "").strip() for n in (order_numbers or []) if str(n or "").strip()]
    if not nos:
        return
    stamps = _load_sheet_entered_at(storage)
    now = datetime.now(KYIV).isoformat(timespec="seconds")
    changed = False
    new_nos: list[str] = []
    for no in nos:
        if no in stamps:
            continue
        stamps[no] = now
        new_nos.append(no)
        changed = True
    if changed:
        _save_sheet_entered_at(storage, stamps)
    if new_nos:
        stages = _load_sheet_stages(storage)
        stage_now = initial_warehouse_stage()
        dirty = False
        for no in new_nos:
            if no not in stages:
                stages[no] = stage_now
                dirty = True
        if dirty:
            _save_sheet_stages(storage, stages)


def _sheet_money(raw: Any) -> float:
    text = str(raw or "").strip().replace(" ", "").replace(",", ".")
    if not text:
        return 0.0
    try:
        return max(0.0, float(text))
    except (TypeError, ValueError):
        return 0.0


def _phone_from_client(text: str) -> str:
    digits = re.sub(r"\D+", "", str(text or ""))
    if len(digits) >= 10:
        return digits[-12:] if len(digits) > 12 else digits
    return ""


def _sheet_status_to_ttn(status: str, ttn: str) -> str:
    from bot.sheet_tracking import is_terminal_sheet_status

    raw = str(status or "").strip()
    folded = raw.casefold()
    has_ttn = bool(str(ttn or "").strip())
    if is_terminal_sheet_status(raw):
        if any(
            w in folded
            for w in (
                "відмов",
                "отказ",
                "повернен",
                "повернут",
                "возврат",
                "скасован",
                "отменен",
            )
        ):
            if "скасован" in folded or "отменен" in folded:
                return "cancelled"
            return "returned"
        return "received"
    if any(word in folded for word in _LEFT_WAREHOUSE_STATUS):
        if any(
            w in folded
            for w in ("відділен", "отделен", "прибув", "прибыл")
        ):
            return "at_warehouse"
        return "in_transit"
    if "помилка" in folded or "ошибка" in folded:
        return "create_error"
    if has_ttn:
        return "created"
    return "none"


def _load_sheet_market_groups(
    storage: AppStorage, *, packing_only: bool
) -> dict[str, list[dict[str, Any]]]:
    try:
        from bot.orders_sheets import _open_orders_worksheet

        ws = _open_orders_worksheet(storage)
        rows = ws.get_all_values()
    except Exception:
        logger.exception("warehouse: failed to read marketplace rows from sheet")
        return {}

    groups: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(rows[1:], start=2):
        while len(row) < 18:
            row.append("")
        order_no = str(row[1] or "").strip()
        source = str(row[10] or "").strip()
        if not order_no or not _is_market_or_manual_source(source, order_no):
            continue
        status = str(row[13] or "").strip()
        groups.setdefault(order_no, []).append(
            {
                "row_idx": idx,
                "created_raw": row[0],
                "payment": str(row[2] or "").strip(),
                "name": str(row[4] or "").strip(),
                "code": str(row[5] or "").strip(),
                "color": str(row[6] or "").strip(),
                "qty": _sheet_qty(row[7]),
                "retail": _sheet_money(row[8]),
                "source": source,
                "carrier": str(row[3] or "").strip(),
                "client": str(row[11] or "").strip(),
                "ttn": str(row[12] or "").strip(),
                "status": status,
                "location": _clean_location(row[17] if len(row) > 17 else ""),
            }
        )
    if not packing_only:
        return groups
    kept: dict[str, list[dict[str, Any]]] = {}
    for order_no, lines in groups.items():
        left = False
        for line in lines:
            status = str(line.get("status") or "").strip()
            if status and not _is_sheet_row_still_packing(status):
                left = True
                break
        if not left:
            kept[order_no] = lines
    return kept


def _sheet_order_from_lines(
    order_no: str,
    lines: list[dict[str, Any]],
    *,
    stages: dict[str, str] | None = None,
    for_history: bool = False,
    entered_at: str = "",
) -> dict[str, Any]:
    lines = sorted(lines, key=lambda x: int(x.get("row_idx") or 0))
    latest = lines[-1]
    ttn = next((str(x.get("ttn") or "").strip() for x in lines if x.get("ttn")), "")
    sources: list[str] = []
    for line in lines:
        src = str(line.get("source") or "").strip()
        if src and src not in sources:
            sources.append(src)
    client = next(
        (str(x.get("client") or "").strip() for x in lines if x.get("client")),
        "",
    )
    payment = next(
        (str(x.get("payment") or "").strip() for x in lines if x.get("payment")),
        "",
    )
    carrier = next(
        (str(x.get("carrier") or "").strip() for x in lines if x.get("carrier")),
        "",
    )
    created_at = str(entered_at or "").strip() or _sheet_created_at(
        latest.get("created_raw"), latest.get("row_idx") or 0
    )
    sheet_created_at = _sheet_created_at(
        latest.get("created_raw"), latest.get("row_idx") or 0
    )
    source_label = " · ".join(sources)
    total = round(sum(float(x.get("retail") or 0) * int(x.get("qty") or 1) for x in lines), 2)
    if for_history:
        ttn_status = _sheet_status_to_ttn(str(latest.get("status") or ""), ttn)
        status = "cancelled" if ttn_status == "cancelled" else "accepted"
    else:
        ttn_status = "created" if ttn else "none"
        status = "new"
    stage = normalize_warehouse_stage((stages or {}).get(order_no) or STAGE_PACKING)
    return {
        "id": sheet_order_id(order_no),
        "order_number": order_no,
        "ttn_number": ttn,
        "own_ttn": False,
        "created_at": created_at,
        "sheet_row": int(latest.get("row_idx") or 0),
        "entered_label": format_warehouse_entered_label(created_at),
        "warehouse_stage": stage,
        "status": status,
        "ttn_status": ttn_status,
        "payment_method": payment,
        "total": total,
        "prepay": 0,
        "payload": {
            "sheet_order": True,
            "sheet_created_at": sheet_created_at,
            "market_source": source_label,
            "warehouse_stage": stage,
            "ttn_number": ttn,
            "carrier": carrier,
            "comment": source_label,
            "recipient": {
                "first_name": client,
                "last_name": "",
                "phone": _phone_from_client(client),
            },
            "payment": {"method": payment},
            "cart": [
                {
                    "name": str(line.get("name") or ""),
                    "code": str(line.get("code") or ""),
                    "color": str(line.get("color") or ""),
                    "qty": int(line.get("qty") or 1),
                    "location": str(line.get("location") or ""),
                    "source": str(line.get("source") or ""),
                    "drop_price": str(line.get("retail") or ""),
                }
                for line in lines
            ],
        },
    }


def _persist_sqlite_left_warehouse(
    storage: AppStorage, order: dict[str, Any], mapped: str
) -> None:
    """Запам'ятати, що посилка вже поїхала — щоб картка не верталась у «На відправлення»."""
    if is_sheet_queue_order(order):
        return
    try:
        oid = int(order.get("id") or 0)
    except (TypeError, ValueError):
        return
    if oid <= 0:
        return
    status = mapped if mapped in SHIPPED_OR_FINAL_STATUSES else "in_transit"
    prev = str(order.get("ttn_status") or "").strip()
    if prev == status:
        return
    try:
        storage.update_order_flags(
            oid, ttn_status=status, warehouse_stage=STAGE_SHIPPED
        )
        storage.merge_order_payload(
            oid,
            {
                "warehouse_stage": STAGE_SHIPPED,
                "warehouse_left_via_tracking": True,
                "warehouse_left_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
    except Exception:
        logger.exception(
            "warehouse: persist left-warehouse failed for %s",
            order.get("order_number"),
        )


def _cached_np_live_statuses(
    storage: AppStorage, ttns: list[str]
) -> dict[str, dict[str, Any]]:
    global _np_live_cache_at, _np_live_cache_key, _np_live_cache_data
    from bot.sheet_tracking import fetch_np_tracking_statuses

    key = frozenset(ttns)
    now = time.monotonic()
    if (
        key
        and key == _np_live_cache_key
        and now - _np_live_cache_at < _NP_LIVE_CACHE_TTL_SEC
    ):
        return _np_live_cache_data
    data = fetch_np_tracking_statuses(storage, ttns)
    if data:
        _np_live_cache_at = now
        _np_live_cache_key = key
        _np_live_cache_data = data
    return data


def _drop_sheet_orders_left_via_np(
    storage: AppStorage, orders: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Прибрати з черги складу посилки, які НП уже везе, навіть якщо стовпець N застарів."""
    from bot.novaposhta import map_np_status_code

    ttns: list[str] = []
    for order in orders:
        raw = str(order.get("ttn_number") or "")
        if str(raw).upper().startswith("RMP-"):
            continue
        digits = re.sub(r"\D+", "", raw)
        if _looks_like_np_ttn(raw) and digits:
            ttns.append(digits)
    if not ttns:
        return orders
    try:
        info = _cached_np_live_statuses(storage, ttns)
    except Exception:
        logger.exception("warehouse: NP live status check failed")
        return orders
    kept: list[dict[str, Any]] = []
    for order in orders:
        raw = str(order.get("ttn_number") or "")
        if str(raw).upper().startswith("RMP-"):
            kept.append(order)
            continue
        digits = re.sub(r"\D+", "", raw)
        row = info.get(digits) or {}
        if not row:
            kept.append(order)
            continue
        mapped = map_np_status_code(row.get("status_code"), row.get("status") or "")
        np_text = str(row.get("status") or "").strip()
        left = mapped in SHIPPED_OR_FINAL_STATUSES or (
            bool(np_text) and not _is_sheet_row_still_packing(np_text)
        )
        if left:
            _persist_sqlite_left_warehouse(storage, order, mapped or "in_transit")
            continue
        kept.append(order)
    return kept


def _is_rozetka_queue_order(order: dict[str, Any]) -> bool:
    payload = order.get("payload") or {}
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "")
    if ttn.upper().startswith("RMP-"):
        return True
    src = str(
        payload.get("market_source") or order.get("source_label") or ""
    ).casefold()
    return "розет" in src or "rozetka" in src


def _cached_rozetka_status_labels(order_nos: list[str]) -> dict[str, str]:
    global _rozetka_live_cache_at, _rozetka_live_cache_key, _rozetka_live_cache_data
    from bot.marketplace_ext import fetch_rozetka_status_labels

    key = frozenset(order_nos)
    now = time.monotonic()
    if (
        key
        and key == _rozetka_live_cache_key
        and now - _rozetka_live_cache_at < _ROZETKA_LIVE_CACHE_TTL_SEC
    ):
        return _rozetka_live_cache_data
    data = fetch_rozetka_status_labels(order_nos)
    if data:
        _rozetka_live_cache_at = now
        _rozetka_live_cache_key = key
        _rozetka_live_cache_data = data
    return data


def _drop_orders_left_via_rozetka(
    storage: AppStorage, orders: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Прибрати Rozetka, які вже передані службі доставки."""
    ids = [
        str(o.get("order_number") or "").strip()
        for o in orders
        if _is_rozetka_queue_order(o) and str(o.get("order_number") or "").strip()
    ]
    if not ids:
        return orders
    try:
        labels = _cached_rozetka_status_labels(ids)
    except Exception:
        logger.exception("warehouse: Rozetka live status check failed")
        return orders
    if not labels:
        return orders
    kept: list[dict[str, Any]] = []
    for order in orders:
        no = str(order.get("order_number") or "").strip()
        label = str(labels.get(no) or "").strip()
        if label and not _is_sheet_row_still_packing(label):
            continue
        kept.append(order)
    return kept


def list_sheet_warehouse_orders(storage: AppStorage) -> list[dict[str, Any]]:
    """Prom / Rozetka / ручні з листа «Заказы», які ще на складі (1 картка = 1 №)."""
    groups = _load_sheet_market_groups(storage, packing_only=True)
    stages = _load_sheet_stages(storage)
    entered = _load_sheet_entered_at(storage)
    orders = [
        _sheet_order_from_lines(
            order_no,
            lines,
            stages=stages,
            for_history=False,
            entered_at=entered.get(order_no, ""),
        )
        for order_no, lines in groups.items()
    ]
    orders = [o for o in orders if not is_sheet_order_stale_for_warehouse(o)]
    return _drop_sheet_orders_left_via_np(storage, orders)


def list_sheet_history_orders(storage: AppStorage) -> list[dict[str, Any]]:
    """Усі Prom / Rozetka / ручні з листа — для історії кабінету власника."""
    groups = _load_sheet_market_groups(storage, packing_only=False)
    stages = _load_sheet_stages(storage)
    out = [
        _sheet_order_from_lines(order_no, lines, stages=stages, for_history=True)
        for order_no, lines in groups.items()
    ]
    out.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return out


def list_owner_form_history(
    storage: AppStorage,
    *,
    owner_chat_id: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Замовлення Mini App власника (якщо є картка дроппера) + Prom/Rozetka/ручні з листа."""
    items: list[dict[str, Any]] = []
    seen_nos: set[str] = set()
    dropper = storage.get_dropper_by_chat(str(owner_chat_id or "").strip()) if owner_chat_id else None
    if dropper:
        sqlite_items = storage.list_orders_for_dropper(dropper.id, limit=limit)
        items.extend(sqlite_items)
        for order in sqlite_items:
            no = str(order.get("order_number") or "").strip()
            if no:
                seen_nos.add(no)
    for order in list_sheet_history_orders(storage):
        no = str(order.get("order_number") or "").strip()
        if no and no in seen_nos:
            continue
        items.append(order)
        if no:
            seen_nos.add(no)
    items.sort(key=lambda o: str(o.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def get_sheet_warehouse_order(
    storage: AppStorage, order_no: str
) -> dict[str, Any] | None:
    no = str(order_no or "").strip()
    if not no:
        return None
    for order in list_sheet_warehouse_orders(storage):
        if str(order.get("order_number") or "").strip() == no:
            return order
    return None


def list_warehouse_queue(
    storage: AppStorage,
    *,
    stage: str,
    limit: int = 300,
) -> list[dict[str, Any]]:
    stage_key = normalize_warehouse_stage(stage)
    if stage_key not in {STAGE_PACKING, STAGE_READY, STAGE_NEXT}:
        stage_key = STAGE_PACKING
    items = storage.list_orders_for_warehouse(limit=limit)
    out: list[dict[str, Any]] = []
    seen_nos: set[str] = set()
    for order in items:
        if not is_packable_order(order):
            continue
        if is_sheet_order_stale_for_warehouse(order):
            continue
        if order_warehouse_stage(order) != stage_key:
            continue
        out.append(order)
        no = str(order.get("order_number") or "").strip()
        if no:
            seen_nos.add(no)
    for order in list_sheet_warehouse_orders(storage):
        no = str(order.get("order_number") or "").strip()
        if no and no in seen_nos:
            continue
        if is_sheet_order_stale_for_warehouse(order):
            continue
        if order_warehouse_stage(order) != stage_key:
            continue
        out.append(order)
        if no:
            seen_nos.add(no)
    out = _drop_sheet_orders_left_via_np(storage, out)
    out = _drop_orders_left_via_rozetka(storage, out)
    out.sort(key=_queue_sort_key, reverse=True)
    return out


def mark_packing_queue_ready_to_ship(
    storage: AppStorage,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    """Усі замовлення з черги «На пакування» → «На відправлення» (один запис стадій листа)."""
    items = list_warehouse_queue(storage, stage=STAGE_PACKING, limit=500)
    stages = _load_sheet_stages(storage)
    moved_sheet: list[str] = []
    moved_sqlite: list[str] = []
    errors: list[dict[str, str]] = []
    for order in items:
        oid = order.get("id")
        sheet_no = parse_sheet_order_id(oid)
        if sheet_no:
            stages[sheet_no] = STAGE_READY
            moved_sheet.append(sheet_no)
            continue
        try:
            mark_order_ready_to_ship(
                storage, oid, actor_user_id=actor_user_id
            )
            moved_sqlite.append(str(oid))
        except Exception as exc:
            errors.append({"id": str(oid or ""), "error": str(exc)})
    if moved_sheet:
        _save_sheet_stages(storage, stages)
    return {
        "count": len(moved_sheet) + len(moved_sqlite),
        "moved_sheet": len(moved_sheet),
        "moved_sqlite": len(moved_sqlite),
        "errors": errors,
    }


def mark_packing_orders_ready_to_ship(
    storage: AppStorage,
    order_ids: list[Any],
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    """Вибрані замовлення з «На пакування» → «На відправлення»."""
    wanted = [str(x or "").strip() for x in (order_ids or []) if str(x or "").strip()]
    if not wanted:
        return {"count": 0, "moved_sheet": 0, "moved_sqlite": 0, "errors": []}
    wanted_set = set(wanted)
    items = list_warehouse_queue(storage, stage=STAGE_PACKING, limit=500)
    stages = _load_sheet_stages(storage)
    moved_sheet: list[str] = []
    moved_sqlite: list[str] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for order in items:
        oid = str(order.get("id") or "").strip()
        if oid not in wanted_set or oid in seen:
            continue
        seen.add(oid)
        sheet_no = parse_sheet_order_id(oid)
        if sheet_no:
            stages[sheet_no] = STAGE_READY
            moved_sheet.append(sheet_no)
            continue
        try:
            mark_order_ready_to_ship(
                storage, oid, actor_user_id=actor_user_id
            )
            moved_sqlite.append(oid)
        except Exception as exc:
            errors.append({"id": oid, "error": str(exc)})
    missing = [oid for oid in wanted if oid not in seen]
    for oid in missing:
        errors.append({"id": oid, "error": "немає в черзі на пакування"})
    if moved_sheet:
        _save_sheet_stages(storage, stages)
    return {
        "count": len(moved_sheet) + len(moved_sqlite),
        "moved_sheet": len(moved_sheet),
        "moved_sqlite": len(moved_sqlite),
        "errors": errors,
    }


def mark_order_ready_to_ship(
    storage: AppStorage,
    order_id: int | str,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    sheet_no = parse_sheet_order_id(order_id)
    if sheet_no:
        order = get_sheet_warehouse_order(storage, sheet_no)
        if order and order_warehouse_stage(order) == STAGE_READY:
            return order
        set_sheet_warehouse_stage(storage, sheet_no, STAGE_READY)
        if not order:
            return {
                "id": sheet_order_id(sheet_no),
                "order_number": sheet_no,
                "warehouse_stage": STAGE_READY,
                "payload": {
                    "sheet_order": True,
                    "warehouse_stage": STAGE_READY,
                    "warehouse_ready_by": str(actor_user_id or ""),
                },
            }
        order["warehouse_stage"] = STAGE_READY
        payload = dict(order.get("payload") or {})
        payload["warehouse_stage"] = STAGE_READY
        payload["warehouse_ready_by"] = str(actor_user_id or "")
        order["payload"] = payload
        return order
    try:
        sqlite_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Замовлення не знайдено") from exc
    order = storage.get_order(sqlite_id)
    if not order:
        raise ValueError("Замовлення не знайдено")
    if not is_packable_order(order):
        raise ValueError("Замовлення вже не в черзі на пакування")
    if order_warehouse_stage(order) == STAGE_READY:
        return order
    storage.set_order_warehouse_stage(sqlite_id, STAGE_READY)
    storage.merge_order_payload(
        sqlite_id,
        {
            "warehouse_stage": STAGE_READY,
            "warehouse_ready_by": str(actor_user_id or ""),
        },
    )
    storage.add_order_change(
        order_id=sqlite_id,
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
    return storage.get_order(sqlite_id) or order


def mark_order_back_to_packing(
    storage: AppStorage,
    order_id: int | str,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    sheet_no = parse_sheet_order_id(order_id)
    if sheet_no:
        order = get_sheet_warehouse_order(storage, sheet_no)
        if not order:
            raise ValueError("Замовлення не знайдено")
        set_sheet_warehouse_stage(storage, sheet_no, STAGE_PACKING)
        order["warehouse_stage"] = STAGE_PACKING
        payload = dict(order.get("payload") or {})
        payload["warehouse_stage"] = STAGE_PACKING
        order["payload"] = payload
        return order
    try:
        sqlite_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Замовлення не знайдено") from exc
    order = storage.get_order(sqlite_id)
    if not order:
        raise ValueError("Замовлення не знайдено")
    storage.set_order_warehouse_stage(sqlite_id, STAGE_PACKING)
    storage.merge_order_payload(
        sqlite_id,
        {"warehouse_stage": STAGE_PACKING},
    )
    storage.add_order_change(
        order_id=sqlite_id,
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
    return storage.get_order(sqlite_id) or order


def mark_next_ship_orders_to_packing(
    storage: AppStorage,
    order_ids: list[Any],
    *,
    actor_user_id: str = "",
    actor_label: str = "Комірник",
) -> dict[str, Any]:
    """Вибрані з «Наступна відправка» → «На пакування» (терміново сьогодні)."""
    wanted = [str(x or "").strip() for x in (order_ids or []) if str(x or "").strip()]
    if not wanted:
        return {"count": 0, "moved_sheet": 0, "moved_sqlite": 0, "errors": []}
    wanted_set = set(wanted)
    items = list_warehouse_queue(storage, stage=STAGE_NEXT, limit=500)
    stages = _load_sheet_stages(storage)
    moved_sheet: list[str] = []
    moved_sqlite: list[str] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for order in items:
        oid = str(order.get("id") or "").strip()
        if oid not in wanted_set or oid in seen:
            continue
        seen.add(oid)
        sheet_no = parse_sheet_order_id(oid)
        if sheet_no:
            stages[sheet_no] = STAGE_PACKING
            moved_sheet.append(sheet_no)
            continue
        try:
            sqlite_id = int(oid)
        except (TypeError, ValueError):
            errors.append({"id": oid, "error": "немає в черзі на наступну відправку"})
            continue
        current = storage.get_order(sqlite_id)
        if not current:
            errors.append({"id": oid, "error": "замовлення не знайдено"})
            continue
        storage.set_order_warehouse_stage(sqlite_id, STAGE_PACKING)
        storage.merge_order_payload(sqlite_id, {"warehouse_stage": STAGE_PACKING})
        storage.add_order_change(
            order_id=sqlite_id,
            order_number=str(current.get("order_number") or ""),
            actor_role="warehouse",
            actor_user_id=str(actor_user_id or ""),
            actor_label=str(actor_label or "Комірник"),
            change_type="status",
            summary="Переміщено на пакування з «Наступна відправка»",
            diff=[
                {
                    "field": "warehouse_stage",
                    "old": STAGE_NEXT,
                    "new": STAGE_PACKING,
                }
            ],
        )
        moved_sqlite.append(oid)
    missing = [oid for oid in wanted if oid not in seen]
    for oid in missing:
        errors.append({"id": oid, "error": "немає в черзі на наступну відправку"})
    if moved_sheet:
        _save_sheet_stages(storage, stages)
    return {
        "count": len(moved_sheet) + len(moved_sqlite),
        "moved_sheet": len(moved_sheet),
        "moved_sqlite": len(moved_sqlite),
        "errors": errors,
    }


def promote_all_next_ship_to_packing(
    storage: AppStorage,
    *,
    actor_user_id: str = "system",
) -> dict[str, Any]:
    """О 21:00: усі next_ship (включно з PDF-hold) → пакування."""
    moved_sqlite: list[str] = []
    for order in storage.list_orders_for_warehouse(limit=800):
        if str(order.get("status") or "") == "cancelled":
            continue
        if order_warehouse_stage(order) != STAGE_NEXT:
            continue
        sqlite_id = int(order["id"])
        storage.set_order_warehouse_stage(sqlite_id, STAGE_PACKING)
        storage.merge_order_payload(sqlite_id, {"warehouse_stage": STAGE_PACKING})
        storage.add_order_change(
            order_id=sqlite_id,
            order_number=str(order.get("order_number") or ""),
            actor_role="warehouse",
            actor_user_id=str(actor_user_id or "system"),
            actor_label="Авто 21:00",
            change_type="status",
            summary="Автоматично переміщено на пакування (21:00)",
            diff=[
                {
                    "field": "warehouse_stage",
                    "old": STAGE_NEXT,
                    "new": STAGE_PACKING,
                }
            ],
        )
        moved_sqlite.append(str(order.get("order_number") or sqlite_id))
    stages = _load_sheet_stages(storage)
    moved_sheet: list[str] = []
    dirty = False
    for no, stage in list(stages.items()):
        if stage != STAGE_NEXT:
            continue
        stages[no] = STAGE_PACKING
        moved_sheet.append(no)
        dirty = True
    if dirty:
        _save_sheet_stages(storage, stages)
    return {
        "count": len(moved_sqlite) + len(moved_sheet),
        "moved_sheet": len(moved_sheet),
        "moved_sqlite": len(moved_sqlite),
        "orders": moved_sqlite[:40],
        "sheet_orders": moved_sheet[:40],
    }


def _load_next_ship_promote_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (NEXT_SHIP_PROMOTE_KEY,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_next_ship_promote_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    payload = json.dumps(state, ensure_ascii=False)
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (NEXT_SHIP_PROMOTE_KEY, payload, _now()),
        )
        conn.commit()


def seconds_until_next_ship_promote(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> float:
    now = now_kyiv(now)
    if allow_current_hour and now.hour == NEXT_SHIP_PROMOTE_HOUR:
        return 0.0
    candidates: list[datetime] = []
    for day_offset in (0, 1, 2):
        day = now.date() + timedelta(days=day_offset)
        target = datetime.combine(
            day, time(NEXT_SHIP_PROMOTE_HOUR, 0), tzinfo=KYIV
        )
        if target > now:
            candidates.append(target)
    target = candidates[0]
    return max(30.0, (target - now).total_seconds())


def run_next_ship_promote_pass(
    storage: AppStorage,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    dt = now_kyiv(now)
    day = dt.date().isoformat()
    state = _load_next_ship_promote_state(storage)
    if not force:
        if dt.hour != NEXT_SHIP_PROMOTE_HOUR:
            return {"ok": True, "skipped": "not_21", "day": day}
        if str(state.get("last_day") or "") == day:
            return {"ok": True, "skipped": True, "day": day}
    result = promote_all_next_ship_to_packing(storage)
    state = {
        "last_day": day,
        "last_at": dt.isoformat(timespec="seconds"),
        "count": int(result.get("count") or 0),
    }
    _save_next_ship_promote_state(storage, state)
    return {"ok": True, "day": day, **result}


def mark_order_shipped(
    storage: AppStorage,
    order_id: int | str,
    *,
    actor_user_id: str = "",
) -> dict[str, Any]:
    """Прибрати замовлення з черги складу вручну (вже віддали НП / службі)."""
    sheet_no = parse_sheet_order_id(order_id)
    left_at = datetime.now().isoformat(timespec="seconds")
    if sheet_no:
        order = get_sheet_warehouse_order(storage, sheet_no)
        set_sheet_warehouse_stage(storage, sheet_no, STAGE_SHIPPED)
        if not order:
            return {
                "id": sheet_order_id(sheet_no),
                "order_number": sheet_no,
                "warehouse_stage": STAGE_SHIPPED,
                "payload": {
                    "sheet_order": True,
                    "warehouse_stage": STAGE_SHIPPED,
                    "warehouse_left_manually": True,
                    "warehouse_left_at": left_at,
                    "warehouse_shipped_by": str(actor_user_id or ""),
                },
            }
        order["warehouse_stage"] = STAGE_SHIPPED
        payload = dict(order.get("payload") or {})
        payload["warehouse_stage"] = STAGE_SHIPPED
        payload["warehouse_left_manually"] = True
        payload["warehouse_left_at"] = left_at
        payload["warehouse_shipped_by"] = str(actor_user_id or "")
        order["payload"] = payload
        return order
    try:
        sqlite_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Замовлення не знайдено") from exc
    order = storage.get_order(sqlite_id)
    if not order:
        raise ValueError("Замовлення не знайдено")
    if str(order.get("status") or "") == "cancelled":
        raise ValueError("Замовлення скасовано")
    prev_stage = order_warehouse_stage(order)
    if prev_stage == STAGE_SHIPPED:
        return order
    prev_ttn = str(order.get("ttn_status") or "none").strip() or "none"
    next_ttn = prev_ttn
    if prev_ttn in PACKABLE_TTN_STATUSES:
        next_ttn = "in_transit"
    flags: dict[str, Any] = {"warehouse_stage": STAGE_SHIPPED}
    if next_ttn != prev_ttn:
        flags["ttn_status"] = next_ttn
    storage.update_order_flags(sqlite_id, **flags)
    storage.merge_order_payload(
        sqlite_id,
        {
            "warehouse_stage": STAGE_SHIPPED,
            "warehouse_left_manually": True,
            "warehouse_left_at": left_at,
            "warehouse_shipped_by": str(actor_user_id or ""),
        },
    )
    storage.add_order_change(
        order_id=sqlite_id,
        order_number=str(order.get("order_number") or ""),
        actor_role="warehouse",
        actor_user_id=str(actor_user_id or ""),
        actor_label="Комірник",
        change_type="status",
        summary="Знято з черги «На відправлення» (вручну)",
        diff=[
            {
                "field": "warehouse_stage",
                "old": prev_stage,
                "new": STAGE_SHIPPED,
            }
        ],
    )
    return storage.get_order(sqlite_id) or order


def order_has_ttn_pdf(order: dict[str, Any]) -> bool:
    payload = order.get("payload") or {}
    if payload.get("sheet_order"):
        ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
        return _looks_like_np_ttn(ttn)
    return bool(
        payload.get("ttn_pdf_local_path")
        or payload.get("ttn_pdf_local_abs")
        or payload.get("ttn_pdf_drive_file_id")
    )


def _download_np_label_pdf(storage: AppStorage, order: dict[str, Any]) -> bytes:
    from bot.np_fulfillment import list_np_clients

    payload = order.get("payload") or {}
    doc_ref = str(payload.get("np_document_ref") or "").strip()
    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    if not doc_ref and not ttn:
        raise ValueError(f"{order.get('order_number')}: немає Ref/ТТН для друку")

    clients = list_np_clients(storage)
    if not clients:
        raise ValueError("Немає API-ключа Нової Пошти для друку етикетки")

    last_err: Exception | None = None
    for label, client, _is_primary in clients:
        try:
            key = doc_ref or ttn
            pdf_bytes = client.download_marking_pdf(key)
            if pdf_bytes:
                return pdf_bytes
        except Exception as exc:
            last_err = exc
            logger.warning(
                "NP label download via «%s» failed order=%s: %s",
                label,
                order.get("order_number"),
                exc,
            )
    raise ValueError(
        f"{order.get('order_number')}: не вдалося завантажити PDF з НП"
        + (f" ({last_err})" if last_err else "")
    ) from last_err


def ensure_order_ttn_pdf(storage: AppStorage, order: dict[str, Any]) -> dict[str, Any]:
    """
    Якщо локального PDF немає — спробувати завантажити етикетку з НП
    (для замовлень, створених ключем власника).
    """
    from bot.ttn_drive import persist_order_ttn_pdf
    from bot.ttn_store import read_pdf_bytes

    payload = order.get("payload") or {}
    if payload.get("sheet_order"):
        if payload.get("_label_pdf_bytes"):
            return order
        pdf_bytes = _download_np_label_pdf(storage, order)
        payload = dict(payload)
        payload["_label_pdf_bytes"] = pdf_bytes
        order["payload"] = payload
        return order

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

    ttn = str(order.get("ttn_number") or payload.get("ttn_number") or "").strip()
    pdf_bytes = _download_np_label_pdf(storage, order)
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
        mem = payload.get("_label_pdf_bytes")
        try:
            if isinstance(mem, (bytes, bytearray)) and mem:
                raw = bytes(mem)
            elif local:
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
