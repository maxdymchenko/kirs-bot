"""Вечірній/ранковий звіт дропперам: зʼявилось / зникло з наявності (10:00 і 20:00 Київ)."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage
from bot.catalog import CatalogService, ProductVariant

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
DIGEST_HOURS = (10, 20)
SETTINGS_KEY = "stock_digest_state"
DEFAULT_CHAT_ID = "-1003582943980"
TELEGRAM_MAX = 3900

NotifyFn = Callable[[str, str], Awaitable[None] | None]


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def _slot_key(day: datetime, hour: int) -> str:
    return f"{day.date().isoformat()}T{hour:02d}"


def _variant_key(code: str, color: str) -> str:
    return f"{str(code or '').strip()}|{str(color or '').strip()}"


def _parse_money(raw: str | None) -> float | None:
    text = str(raw or "").strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return None
    text = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _fmt_money(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _ua_color_genitive_plural(color: str) -> str:
    """коричневий → коричневих; білий → білих."""
    c = str(color or "").strip().casefold()
    if not c:
        return ""
    if c.endswith("ій"):
        return c[:-2] + "іх"
    if c.endswith("ий"):
        return c[:-2] + "их"
    if c.endswith("а"):
        return c[:-1] + "их"
    return c


def _ua_color_nominative_plural(color: str) -> str:
    """чорний → чорні; білий → білі."""
    c = str(color or "").strip().casefold()
    if not c:
        return ""
    if c.endswith("ій"):
        return c[:-2] + "ї"
    if c.endswith("ий"):
        return c[:-2] + "і"
    if c.endswith("а"):
        return c[:-1] + "і"
    return c


def build_stock_map(variants: list[ProductVariant]) -> dict[str, dict[str, Any]]:
    """code|color → {stock, drop, retail, code, color}."""
    out: dict[str, dict[str, Any]] = {}
    for v in variants:
        code = str(v.code or "").strip()
        if not code:
            continue
        if v.stock is None:
            continue
        key = _variant_key(code, v.color)
        stock = max(0, int(v.stock))
        prev = out.get(key)
        if prev is None or stock > int(prev.get("stock") or 0):
            out[key] = {
                "code": code,
                "color": str(v.color or "").strip(),
                "stock": stock,
                "drop": _parse_money(v.drop_price),
                "retail": _parse_money(getattr(v, "retail_price", "") or ""),
            }
    return out


def snapshot_from_map(stock_map: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {k: int(v["stock"]) for k, v in stock_map.items()}


def diff_stock_changes(
    previous: dict[str, int],
    current_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Повертає (gone, appeared) — зміни на рівні code+color.
    gone: було >0 → стало 0 (або рядок зник)
    appeared: було 0/немає → стало >0
    """
    current_snap = snapshot_from_map(current_map)
    gone: list[dict[str, Any]] = []
    appeared: list[dict[str, Any]] = []

    all_keys = set(previous) | set(current_snap)
    for key in all_keys:
        prev = int(previous.get(key) or 0)
        curr = int(current_snap.get(key) or 0)
        meta = current_map.get(key) or {}
        code, _, color = key.partition("|")
        code = str(meta.get("code") or code).strip()
        color = str(meta.get("color") or color).strip()
        if prev > 0 and curr <= 0:
            gone.append(
                {
                    "code": code,
                    "color": color,
                    "drop": meta.get("drop"),
                    "retail": meta.get("retail"),
                }
            )
        elif prev <= 0 and curr > 0:
            appeared.append(
                {
                    "code": code,
                    "color": color,
                    "drop": meta.get("drop"),
                    "retail": meta.get("retail"),
                }
            )
    return gone, appeared


def _group_by_code(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        code = str(row.get("code") or "").strip()
        if code:
            grouped[code].append(row)
    return grouped


def _price_suffix(drop: float | None, retail: float | None) -> str:
    parts: list[str] = []
    if drop is not None:
        parts.append(f"дроп ціна: {_fmt_money(drop)} грн")
    if retail is not None:
        parts.append(f"РРЦ: від {_fmt_money(retail)} грн")
    if not parts:
        return ""
    return f" ({', '.join(parts)})"


def _pick_prices(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    drops = [r.get("drop") for r in rows if r.get("drop") is not None]
    retails = [r.get("retail") for r in rows if r.get("retail") is not None]
    drop = min(drops) if drops else None
    retail = min(retails) if retails else None
    return drop, retail


def format_gone_lines(
    gone: list[dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Рядки під заголовок 🚫НЕМАЄ В НАЯВНОСТІ🚫."""
    lines: list[str] = []
    by_code = _group_by_code(gone)
    for code in sorted(by_code.keys(), key=lambda c: (len(c), c)):
        rows = by_code[code]
        colors_gone = [
            str(r.get("color") or "").strip() for r in rows if str(r.get("color") or "").strip()
        ]
        still_in = any(
            meta.get("code") == code and int(meta.get("stock") or 0) > 0
            for meta in current_map.values()
        )
        if not still_in:
            lines.append(f"{code} - немає в наявності;")
            continue
        if not colors_gone:
            lines.append(f"{code} - немає в наявності;")
            continue
        if len(colors_gone) == 1:
            gen = _ua_color_genitive_plural(colors_gone[0])
            lines.append(f"{code} - немає {gen};")
        else:
            gens = ", ".join(_ua_color_genitive_plural(c) for c in colors_gone)
            lines.append(f"{code} - немає {gens};")
    return lines


def format_appeared_lines(
    appeared: list[dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Рядки під заголовок 🔔ЗНОВУ В НАЯВНОСТІ🔔."""
    lines: list[str] = []
    by_code = _group_by_code(appeared)
    for code in sorted(by_code.keys(), key=lambda c: (len(c), c)):
        rows = by_code[code]
        colors_in = [str(r.get("color") or "").strip() for r in rows]
        colors_in = [c for c in colors_in if c]
        drop, retail = _pick_prices(rows)
        # Якщо в meta цін немає — візьмемо з current_map
        if drop is None or retail is None:
            for meta in current_map.values():
                if meta.get("code") != code:
                    continue
                if drop is None and meta.get("drop") is not None:
                    drop = meta.get("drop")
                if retail is None and meta.get("retail") is not None:
                    retail = meta.get("retail")

        all_colors = [
            meta
            for meta in current_map.values()
            if meta.get("code") == code
        ]
        in_stock_colors = [
            str(m.get("color") or "").strip()
            for m in all_colors
            if int(m.get("stock") or 0) > 0
        ]
        in_stock_colors = [c for c in in_stock_colors if c]
        tracked_colors = [
            str(m.get("color") or "").strip() for m in all_colors if str(m.get("color") or "").strip()
        ]

        suffix = _price_suffix(drop, retail)
        if not colors_in:
            lines.append(f"{code} - в наявності{suffix};")
            continue

        # Усі кольори коду зараз >0 і зʼявився хоча б один
        if (
            tracked_colors
            and len(in_stock_colors) == len(set(tracked_colors))
            and len(set(tracked_colors)) >= 2
        ):
            n = len(set(tracked_colors))
            phrase = "обидва кольори" if n == 2 else "всі кольори"
            lines.append(f"{code} - в наявності {phrase}{suffix};")
            continue

        if len(colors_in) == 1:
            nom = _ua_color_nominative_plural(colors_in[0])
            lines.append(f"{code} - в наявності {nom}{suffix};")
        else:
            noms = ", ".join(_ua_color_nominative_plural(c) for c in colors_in)
            lines.append(f"{code} - в наявності {noms}{suffix};")
    return lines


def build_digest_messages(
    gone: list[dict[str, Any]],
    appeared: list[dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
) -> list[str]:
    messages: list[str] = []
    if gone:
        body = "\n".join(format_gone_lines(gone, current_map))
        messages.extend(_chunk_message("🚫НЕМАЄ В НАЯВНОСТІ🚫", body))
    if appeared:
        body = "\n".join(format_appeared_lines(appeared, current_map))
        messages.extend(_chunk_message("🔔ЗНОВУ В НАЯВНОСТІ🔔", body))
    return messages


def _chunk_message(header: str, body: str) -> list[str]:
    body = body.strip()
    if not body:
        return []
    full = f"{header}\n{body}"
    if len(full) <= TELEGRAM_MAX:
        return [full]
    lines = body.split("\n")
    chunks: list[str] = []
    buf: list[str] = []
    for line in lines:
        trial = "\n".join([header, *buf, line])
        if buf and len(trial) > TELEGRAM_MAX:
            chunks.append("\n".join([header, *buf]))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        chunks.append("\n".join([header, *buf]))
    return chunks


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {"sent": [], "stocks": {}}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {"sent": [], "stocks": {}}
    if not isinstance(data, dict):
        return {"sent": [], "stocks": {}}
    sent = data.get("sent")
    if not isinstance(sent, list):
        sent = []
    stocks = data.get("stocks")
    if not isinstance(stocks, dict):
        stocks = {}
    cleaned = {}
    for k, v in stocks.items():
        try:
            cleaned[str(k)] = max(0, int(v))
        except (TypeError, ValueError):
            continue
    return {"sent": [str(x) for x in sent][-90:], "stocks": cleaned}


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    from bot.accounts import _now

    payload = json.dumps(
        {
            "sent": list(state.get("sent") or [])[-90:],
            "stocks": state.get("stocks") or {},
        },
        ensure_ascii=False,
    )
    with storage._connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (SETTINGS_KEY, payload, _now()),
        )
        conn.commit()


def seconds_until_next_stock_digest(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> tuple[float, int]:
    now = now_kyiv(now)
    if allow_current_hour and now.hour in DIGEST_HOURS:
        return 0.0, now.hour

    candidates: list[tuple[datetime, int]] = []
    for day_offset in (0, 1, 2):
        day = now.date() + timedelta(days=day_offset)
        for hour in DIGEST_HOURS:
            target = datetime.combine(day, time(hour, 0), tzinfo=KYIV)
            if target > now:
                candidates.append((target, hour))
    candidates.sort(key=lambda x: x[0])
    target, hour = candidates[0]
    return max(30.0, (target - now).total_seconds()), hour


async def run_stock_digest_pass(
    storage: AppStorage,
    catalog: CatalogService,
    notify: NotifyFn,
    *,
    chat_id: str,
    now: datetime | None = None,
    hour: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Порівняти поточні залишки (стовпець F) зі знімком і за потреби надіслати 2 списки.
    Перший запуск лише зберігає знімок (без розсилки), щоб не заспамити весь каталог.
    """
    import asyncio

    now = now_kyiv(now)
    slot_hour = int(hour if hour is not None else now.hour)
    target = str(chat_id or "").strip() or DEFAULT_CHAT_ID
    stats: dict[str, Any] = {
        "hour": slot_hour,
        "gone": 0,
        "appeared": 0,
        "messages": 0,
        "sent": 0,
        "skipped": 0,
        "bootstrap": 0,
        "errors": 0,
        "chat_id": target,
    }
    if slot_hour not in DIGEST_HOURS and not force:
        stats["skipped"] = 1
        return stats

    key = _slot_key(now, slot_hour)
    state = _load_state(storage)
    if key in state["sent"] and not force:
        stats["skipped"] = 1
        return stats

    try:
        variants = await asyncio.to_thread(catalog.all_variants, True)
    except Exception:
        stats["errors"] = 1
        logger.exception("stock digest: catalog refresh failed")
        return stats

    current_map = build_stock_map(variants)
    previous = state.get("stocks") or {}

    if not previous:
        state["stocks"] = snapshot_from_map(current_map)
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["bootstrap"] = 1
        stats["skipped"] = 1
        logger.info(
            "stock digest bootstrap: saved %d stock rows, no broadcast",
            len(state["stocks"]),
        )
        return stats

    gone, appeared = diff_stock_changes(previous, current_map)
    stats["gone"] = len(gone)
    stats["appeared"] = len(appeared)

    # Завжди оновлюємо знімок після перевірки
    state["stocks"] = snapshot_from_map(current_map)

    if not gone and not appeared:
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["skipped"] = 1
        return stats

    messages = build_digest_messages(gone, appeared, current_map)
    stats["messages"] = len(messages)
    try:
        for text in messages:
            result = notify(target, text)
            if hasattr(result, "__await__"):
                await result
        state["sent"] = [*(state.get("sent") or []), key]
        _save_state(storage, state)
        stats["sent"] = 1
    except Exception:
        stats["errors"] = 1
        logger.exception("stock digest notify failed hour=%s chat=%s", slot_hour, target)
        _save_state(storage, state)
    return stats
