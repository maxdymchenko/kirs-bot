"""Публічний трекінг Rozetka Delivery (RMP-…)."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

RMP_API_BASE = "https://rz-delivery.rozetka.ua/api/"
RMP_PUBLIC_TRACK_URL = RMP_API_BASE + "track/public/{track_id}"

_RMP_ID_RE = re.compile(r"^RMP-?(\d{6,20})$", re.IGNORECASE)

_RMP_RECEIVED = frozenset({60025, 60030})
_RMP_WAREHOUSE = frozenset({40030, 40040, 40080})
_RMP_REFUSED = frozenset({40050})
_RMP_RETURN_WAREHOUSE = frozenset({50020})
_RMP_RETURNED = frozenset(
    {
        40045,
        40060,
        40070,
        50010,
        50011,
        50012,
        50013,
        50015,
        50021,
        50030,
        60040,
    }
)
_RMP_FAILED = frozenset({10060, 60010, 10080})

_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Language": "uk",
    "Origin": "https://rozetka.delivery",
    "Referer": "https://rozetka.delivery/tracking/parcel",
    "User-Agent": "KirsBot/1.0",
}


class RmpTrackingError(Exception):
    def __init__(
        self,
        message: str,
        *,
        not_found: bool = False,
        invalid: bool = False,
        throttled: bool = False,
    ) -> None:
        super().__init__(message)
        self.not_found = not_found
        self.invalid = invalid
        self.throttled = throttled


def normalize_rmp_track_id(raw: str) -> str:
    """Офіційний формат: RMP- + 9 цифр або 12 цифр без префікса."""
    text = str(raw or "").strip().upper().replace(" ", "")
    if not text:
        return ""
    match = _RMP_ID_RE.fullmatch(text)
    if match:
        digits = match.group(1)
        if len(digits) <= 9:
            return f"RMP-{digits.zfill(9)}"
        if len(digits) == 12:
            return digits
        return f"RMP-{digits}"
    digits = re.sub(r"\D+", "", text)
    if len(digits) == 12:
        return digits
    return ""


def is_rmp_trackable_number(raw: str) -> bool:
    return bool(normalize_rmp_track_id(raw))


def order_rmp_trackable(order: dict[str, Any] | None) -> bool:
    if not order:
        return False
    payload = order.get("payload") if isinstance(order.get("payload"), dict) else {}
    carrier = str(payload.get("own_ttn_carrier") or "").strip().lower().replace("-", "_")
    number = str(order.get("ttn_number") or "")
    if is_rmp_trackable_number(number):
        return True
    return carrier in {"rozetka", "rz", "rmp"} and bool(normalize_rmp_track_id(number))


def map_rmp_status(status_code: str | int | None, status_text: str = "") -> str:
    try:
        code = int(str(status_code or "").strip())
    except (TypeError, ValueError):
        code = 0
    if code in _RMP_RECEIVED:
        return "received"
    if code in _RMP_WAREHOUSE:
        return "at_warehouse"
    if code in _RMP_REFUSED:
        return "refused"
    if code in _RMP_RETURN_WAREHOUSE:
        return "return_at_warehouse"
    if code in _RMP_RETURNED:
        return "returned"
    if code in _RMP_FAILED:
        return "failed"

    text = str(status_text or "").casefold()
    if any(word in text for word in ("видано", "частично отрим", "issued")):
        return "received"
    if any(word in text for word in ("відмовив", "отказ", "refuse")):
        return "refused"
    if any(
        word in text
        for word in ("поверн", "возврат", "термін зберіг", "очікує відправника")
    ):
        if "очікує відправника" in text:
            return "return_at_warehouse"
        return "returned"
    if any(
        word in text
        for word in ("готово до видачі", "у відділенні", "відділенні доставки")
    ):
        return "at_warehouse"
    if any(word in text for word in ("скасов", "втрачен", "видален")):
        return "failed"
    return "in_transit" if (code or text) else "unknown"


def fetch_rmp_public_status(track_id: str) -> dict[str, Any] | None:
    """
    GET /track/public/{id}.
    None = накладну не знайдено. Incomplete / throttle / invalid — виняток.
    """
    tid = normalize_rmp_track_id(track_id) or str(track_id or "").strip()
    if not tid:
        raise RmpTrackingError("empty id", invalid=True)
    url = RMP_PUBLIC_TRACK_URL.format(track_id=urllib.parse.quote(tid, safe="-"))
    req = urllib.request.Request(url, headers=_REQUEST_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        if exc.code == 404:
            return None
        if exc.code == 429:
            raise RmpTrackingError("throttled", throttled=True) from exc
        if exc.code == 400:
            raise RmpTrackingError("invalid format", invalid=True) from exc
        raise RmpTrackingError(f"HTTP {exc.code}: {body[:180]}") from exc
    except urllib.error.URLError as exc:
        raise RmpTrackingError("network") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RmpTrackingError("bad json") from exc
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def tracking_row_from_rmp(data: dict[str, Any], track_id: str) -> dict[str, Any]:
    status_date = str(data.get("last_status_date") or "").strip()
    return {
        "Number": str(data.get("id") or track_id),
        "StatusCode": data.get("last_status"),
        "Status": str(data.get("last_status_name") or "").strip(),
        "last_status": data.get("last_status"),
        "last_status_name": data.get("last_status_name"),
        "last_status_date": status_date,
        "delivery_date": data.get("delivery_date"),
        "DateScan": status_date,
        "return_type": data.get("return_type"),
    }


def fetch_rmp_status_with_retry(track_id: str) -> dict[str, Any] | None:
    try:
        return fetch_rmp_public_status(track_id)
    except RmpTrackingError as exc:
        if exc.throttled:
            time.sleep(2.5)
            return fetch_rmp_public_status(track_id)
        if exc.invalid or exc.not_found:
            return None
        raise
