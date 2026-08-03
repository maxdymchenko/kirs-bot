"""Очередь закупок владельца: коды «заказать» + утренний дайджест 9:00 Киев."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, time, timedelta
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from bot.accounts import AppStorage, _now

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
NOTIFY_HOUR = 9
SETTINGS_KEY = "to_order_digest_state"

# «1231 - заказан» / «1231 — замовлено»
_ORDERED_RE = re.compile(
    r"^\s*(?P<code>.+?)\s*[-–—]\s*(?:заказан[ао]?|замовлено|заказано)\s*$",
    re.IGNORECASE,
)

NotifyFn = Callable[[str, str], Awaitable[None] | None]
OwnerNotifyFn = Callable[[str], Awaitable[None] | None]


def now_kyiv(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(KYIV)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KYIV)
    return dt.astimezone(KYIV)


def parse_ordered_code(text: str) -> str | None:
    match = _ORDERED_RE.match(str(text or "").strip())
    if not match:
        return None
    code = AppStorage.normalize_to_order_code(match.group("code"))
    return code or None


def parse_to_order_codes(text: str) -> list[str]:
    """Коды из сообщения: по одному в строке (или через запятую в строке)."""
    codes: list[str] = []
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if parse_ordered_code(line):
            continue
        parts = re.split(r"[,;]+", line) if ("," in line or ";" in line) else [line]
        for part in parts:
            code = AppStorage.normalize_to_order_code(part)
            if not code:
                continue
            key = code.casefold()
            if key in seen:
                continue
            seen.add(key)
            codes.append(code)
    return codes


def format_pending_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Список «Замовити» порожній."
    lines = [f"📋 Замовити ({len(items)}):", ""]
    for item in items:
        lines.append(f"• {item.get('product_code') or '—'}")
    lines.append("")
    lines.append("Коли замовите — напишіть: `код - заказан`")
    return "\n".join(lines)


def format_morning_digest(items: list[dict[str, Any]]) -> str:
    lines = [
        f"📦 Замовити на сьогодні ({len(items)}):",
        "",
    ]
    for item in items:
        lines.append(f"• {item.get('product_code') or '—'}")
    lines.append("")
    lines.append("Після замовлення: `код - заказан` — і код зникне зі списку.")
    return "\n".join(lines)


def seconds_until_next_to_order_hour(
    *,
    now: datetime | None = None,
    allow_current_hour: bool = False,
) -> float:
    now = now_kyiv(now)
    if allow_current_hour and now.hour == NOTIFY_HOUR:
        return 0.0
    target = datetime.combine(now.date(), time(NOTIFY_HOUR, 0), tzinfo=KYIV)
    if now >= target:
        target = target + timedelta(days=1)
    return max(30.0, (target - now).total_seconds())


def _slot_key(day: datetime) -> str:
    return f"{day.date().isoformat()}T{NOTIFY_HOUR:02d}"


def _load_state(storage: AppStorage) -> dict[str, Any]:
    with storage._connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?",
            (SETTINGS_KEY,),
        ).fetchone()
    if not row:
        return {"sent": []}
    try:
        data = json.loads(row["value_json"] or "{}")
    except json.JSONDecodeError:
        return {"sent": []}
    if not isinstance(data, dict):
        return {"sent": []}
    sent = data.get("sent")
    if not isinstance(sent, list):
        sent = []
    return {"sent": [str(x) for x in sent][-30:]}


def _save_state(storage: AppStorage, state: dict[str, Any]) -> None:
    payload = json.dumps(
        {"sent": list(state.get("sent") or [])[-30:]},
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


async def run_to_order_digest_pass(
    storage: AppStorage,
    owner_notify: OwnerNotifyFn,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, int]:
    """О 9:00 Київ — список кодів «замовити» власнику. Порожній список — без повідомлення."""
    now = now_kyiv(now)
    stats = {"sent": 0, "skipped_empty": 0, "skipped_slot": 0, "items": 0}
    if not force and now.hour != NOTIFY_HOUR:
        stats["skipped_slot"] = 1
        return stats

    slot = _slot_key(now)
    state = _load_state(storage)
    if not force and slot in (state.get("sent") or []):
        stats["skipped_slot"] = 1
        return stats

    items = storage.list_to_order_pending(limit=500)
    stats["items"] = len(items)
    if not items:
        state["sent"] = list(state.get("sent") or []) + [slot]
        _save_state(storage, state)
        stats["skipped_empty"] = 1
        return stats

    text = format_morning_digest(items)
    try:
        await owner_notify(text)
        stats["sent"] = 1
    except Exception:
        logger.exception("to_order digest notify failed")
        raise

    state["sent"] = list(state.get("sent") or []) + [slot]
    _save_state(storage, state)
    return stats
