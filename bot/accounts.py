"""SQLite: дропперы, сотрудники, миграции chat_id."""

from __future__ import annotations

import calendar
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.paths import app_db_path

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_referral_code() -> str:
    return secrets.token_hex(3).upper()


def _norm_staff_username(value: str | None) -> str:
    raw = str(value or "").strip()
    if raw.startswith("@"):
        raw = raw[1:]
    return raw.lower()


def _parse_iso_dt(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _add_months_iso(start_iso: str, months: int) -> str:
    dt = _parse_iso_dt(start_iso) or datetime.now(timezone.utc)
    months = max(0, int(months or 0))
    month_idx = dt.month - 1 + months
    year = dt.year + month_idx // 12
    month = month_idx % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day).isoformat()


@dataclass
class Dropper:
    id: int
    chat_id: str
    company_name: str
    contact_name: str
    phone: str
    comment: str
    require_full_payment: bool
    allow_cod: bool
    allow_balance_payment: bool
    allow_negative_balance: bool
    negative_balance_limit: float
    extra_discount_percent: float
    orders_disabled: bool
    owner_comment: str
    credit_holidays_days: int
    credit_debt_started_at: str | None
    credit_holidays_blocked: bool
    credit_last_notified_at: str | None
    notify_shipping_events: bool
    referral_code: str
    referral_program_enabled: bool
    referral_months: int
    referred_by_dropper_id: int | None
    referral_percent: float
    referral_expires_at: str | None
    buyout_percent: float | None
    buyout_tier: str
    buyout_tier_notified: str
    buyout_half_warned: bool
    status: str
    registered_by_user_id: str
    registered_by_username: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "company_name": self.company_name,
            "contact_name": self.contact_name,
            "phone": self.phone,
            "comment": self.comment,
            "require_full_payment": self.require_full_payment,
            "allow_cod": self.allow_cod,
            "allow_balance_payment": self.allow_balance_payment,
            "allow_negative_balance": self.allow_negative_balance,
            "negative_balance_limit": self.negative_balance_limit,
            "extra_discount_percent": self.extra_discount_percent,
            "orders_disabled": self.orders_disabled,
            "owner_comment": self.owner_comment,
            "credit_holidays_days": self.credit_holidays_days,
            "credit_debt_started_at": self.credit_debt_started_at,
            "credit_holidays_blocked": self.credit_holidays_blocked,
            "credit_last_notified_at": self.credit_last_notified_at,
            "notify_shipping_events": self.notify_shipping_events,
            "referral_code": self.referral_code,
            "referral_program_enabled": self.referral_program_enabled,
            "referral_months": self.referral_months,
            "referred_by_dropper_id": self.referred_by_dropper_id,
            "referral_percent": self.referral_percent,
            "referral_expires_at": self.referral_expires_at,
            "buyout_percent": self.buyout_percent,
            "buyout_tier": self.buyout_tier,
            "buyout_tier_notified": self.buyout_tier_notified,
            "buyout_half_warned": self.buyout_half_warned,
            "status": self.status,
            "registered_by_user_id": self.registered_by_user_id,
            "registered_by_username": self.registered_by_username,
            "created_at": self.created_at,
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Без owner_comment — для відповідей дропперу.
        Якщо реферальна програма вимкнена — не віддаємо код/%/строк, щоб у UI не було згадок.
        """
        data = self.to_dict()
        data.pop("owner_comment", None)
        if not self.referral_program_enabled:
            data["referral_code"] = ""
            data["referral_percent"] = 0
            data["referral_months"] = 0
            data["referral_expires_at"] = None
        return data


@dataclass
class StaffMember:
    id: int
    telegram_user_id: str
    username: str
    full_name: str
    role: str
    active: bool
    created_at: str
    created_by_user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "telegram_user_id": self.telegram_user_id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "active": self.active,
            "created_at": self.created_at,
            "created_by_user_id": self.created_by_user_id,
        }


class AppStorage:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or app_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {
            str(r["name"])
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS droppers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL UNIQUE,
                    company_name TEXT NOT NULL,
                    contact_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    require_full_payment INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    registered_by_user_id TEXT NOT NULL DEFAULT '',
                    registered_by_username TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            for column, ddl in (
                ("allow_balance_payment", "allow_balance_payment INTEGER NOT NULL DEFAULT 0"),
                ("allow_negative_balance", "allow_negative_balance INTEGER NOT NULL DEFAULT 0"),
                ("negative_balance_limit", "negative_balance_limit REAL NOT NULL DEFAULT 0"),
                ("extra_discount_percent", "extra_discount_percent REAL NOT NULL DEFAULT 0"),
                ("orders_disabled", "orders_disabled INTEGER NOT NULL DEFAULT 0"),
                ("allow_cod", "allow_cod INTEGER NOT NULL DEFAULT 1"),
                ("referral_code", "referral_code TEXT NOT NULL DEFAULT ''"),
                ("referred_by_dropper_id", "referred_by_dropper_id INTEGER"),
                ("referral_percent", "referral_percent REAL NOT NULL DEFAULT 0"),
                ("owner_comment", "owner_comment TEXT NOT NULL DEFAULT ''"),
                ("credit_holidays_days", "credit_holidays_days INTEGER NOT NULL DEFAULT 0"),
                ("credit_debt_started_at", "credit_debt_started_at TEXT"),
                ("credit_holidays_blocked", "credit_holidays_blocked INTEGER NOT NULL DEFAULT 0"),
                ("credit_last_notified_at", "credit_last_notified_at TEXT"),
                ("notify_shipping_events", "notify_shipping_events INTEGER NOT NULL DEFAULT 0"),
                ("referral_program_enabled", "referral_program_enabled INTEGER NOT NULL DEFAULT 0"),
                ("referral_months", "referral_months INTEGER NOT NULL DEFAULT 12"),
                ("referral_expires_at", "referral_expires_at TEXT"),
                ("buyout_percent", "buyout_percent REAL"),
                ("buyout_tier", "buyout_tier TEXT NOT NULL DEFAULT ''"),
                ("buyout_tier_notified", "buyout_tier_notified TEXT NOT NULL DEFAULT ''"),
                ("buyout_half_warned", "buyout_half_warned INTEGER NOT NULL DEFAULT 0"),
            ):
                self._ensure_column(conn, "droppers", column, ddl)

            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_droppers_referral_code
                ON droppers(referral_code)
                WHERE referral_code != ''
                """
            )

            # Старі дроппери з % > 0 — програму вважаємо увімкненою
            conn.execute(
                """
                UPDATE droppers
                SET referral_program_enabled = 1
                WHERE referral_percent > 0
                  AND (referral_program_enabled IS NULL OR referral_program_enabled = 0)
                  AND referral_code IS NOT NULL AND referral_code != ''
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS referral_fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint_type TEXT NOT NULL,
                    fingerprint_value TEXT NOT NULL,
                    first_dropper_id INTEGER,
                    first_seen_at TEXT NOT NULL,
                    UNIQUE(fingerprint_type, fingerprint_value)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS phone_blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_digits TEXT NOT NULL UNIQUE,
                    phone_display TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT NOT NULL DEFAULT ''
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL DEFAULT '',
                    full_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_migrations (
                    old_chat_id TEXT PRIMARY KEY,
                    new_chat_id TEXT NOT NULL,
                    migrated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_migrations_new
                ON chat_migrations(new_chat_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS balance_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dropper_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    entry_type TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    related_order_id TEXT NOT NULL DEFAULT '',
                    related_dropper_id INTEGER,
                    meta_json TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_balance_ledger_dropper
                ON balance_ledger(dropper_id, id DESC)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_balance_ledger_idempotent
                ON balance_ledger(dropper_id, entry_type, related_order_id)
                WHERE related_order_id != ''
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number TEXT NOT NULL UNIQUE,
                    dropper_id INTEGER NOT NULL,
                    chat_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'accepted',
                    payment_method TEXT NOT NULL DEFAULT '',
                    delivery_method TEXT NOT NULL DEFAULT '',
                    own_ttn INTEGER NOT NULL DEFAULT 0,
                    total REAL NOT NULL DEFAULT 0,
                    prepay REAL NOT NULL DEFAULT 0,
                    prepay_balance_debit REAL NOT NULL DEFAULT 0,
                    cod_amount REAL NOT NULL DEFAULT 0,
                    ttn_number TEXT NOT NULL DEFAULT '',
                    ttn_status TEXT NOT NULL DEFAULT 'none',
                    sheets_sync_status TEXT NOT NULL DEFAULT 'pending',
                    notify_dropper_status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_dropper
                ON orders(dropper_id, id DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_created
                ON orders(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _row_get(self, row: sqlite3.Row, key: str, default: Any = None) -> Any:
        try:
            return row[key]
        except (IndexError, KeyError):
            return default

    def _row_dropper(self, row: sqlite3.Row) -> Dropper:
        ref_by = self._row_get(row, "referred_by_dropper_id")
        return Dropper(
            id=row["id"],
            chat_id=row["chat_id"],
            company_name=row["company_name"],
            contact_name=row["contact_name"],
            phone=row["phone"],
            comment=row["comment"] or "",
            require_full_payment=bool(row["require_full_payment"]),
            allow_cod=bool(self._row_get(row, "allow_cod", 1)),
            allow_balance_payment=bool(self._row_get(row, "allow_balance_payment", 0)),
            allow_negative_balance=bool(self._row_get(row, "allow_negative_balance", 0)),
            negative_balance_limit=float(self._row_get(row, "negative_balance_limit", 0) or 0),
            extra_discount_percent=float(self._row_get(row, "extra_discount_percent", 0) or 0),
            orders_disabled=bool(self._row_get(row, "orders_disabled", 0)),
            owner_comment=str(self._row_get(row, "owner_comment", "") or ""),
            credit_holidays_days=int(self._row_get(row, "credit_holidays_days", 0) or 0),
            credit_debt_started_at=(
                str(self._row_get(row, "credit_debt_started_at") or "").strip() or None
            ),
            credit_holidays_blocked=bool(self._row_get(row, "credit_holidays_blocked", 0)),
            credit_last_notified_at=(
                str(self._row_get(row, "credit_last_notified_at") or "").strip() or None
            ),
            notify_shipping_events=bool(self._row_get(row, "notify_shipping_events", 0)),
            referral_code=str(self._row_get(row, "referral_code", "") or ""),
            referral_program_enabled=bool(self._row_get(row, "referral_program_enabled", 0)),
            referral_months=max(0, int(self._row_get(row, "referral_months", 12) or 12)),
            referred_by_dropper_id=int(ref_by) if ref_by not in (None, "") else None,
            referral_percent=float(self._row_get(row, "referral_percent", 0) or 0),
            referral_expires_at=(
                str(self._row_get(row, "referral_expires_at") or "").strip() or None
            ),
            buyout_percent=(
                float(self._row_get(row, "buyout_percent"))
                if self._row_get(row, "buyout_percent") not in (None, "")
                else None
            ),
            buyout_tier=str(self._row_get(row, "buyout_tier", "") or ""),
            buyout_tier_notified=str(self._row_get(row, "buyout_tier_notified", "") or ""),
            buyout_half_warned=bool(self._row_get(row, "buyout_half_warned", 0)),
            status=row["status"],
            registered_by_user_id=row["registered_by_user_id"] or "",
            registered_by_username=row["registered_by_username"] or "",
            created_at=row["created_at"],
        )

    def _row_staff(self, row: sqlite3.Row) -> StaffMember:
        return StaffMember(
            id=row["id"],
            telegram_user_id=row["telegram_user_id"],
            username=row["username"] or "",
            full_name=row["full_name"] or "",
            role=row["role"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            created_by_user_id=row["created_by_user_id"] or "",
        )

    def resolve_chat_id(self, chat_id: str | int | None) -> str:
        key = str(chat_id or "").strip()
        if not key:
            return ""
        seen: set[str] = set()
        with self._connect() as conn:
            while key and key not in seen:
                seen.add(key)
                row = conn.execute(
                    "SELECT new_chat_id FROM chat_migrations WHERE old_chat_id = ?",
                    (key,),
                ).fetchone()
                if not row:
                    break
                key = str(row["new_chat_id"]).strip()
        return key

    def migrate_chat_id(self, old_chat_id: str | int, new_chat_id: str | int) -> dict[str, Any]:
        old_id = str(old_chat_id).strip()
        new_id = str(new_chat_id).strip()
        if not old_id or not new_id or old_id == new_id:
            return {"ok": False, "reason": "invalid", "old": old_id, "new": new_id}

        now = _now()
        updated_dropper = False
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT new_chat_id FROM chat_migrations WHERE old_chat_id = ?",
                (old_id,),
            ).fetchone()
            if not (existing and str(existing["new_chat_id"]) == new_id):
                conn.execute(
                    """
                    INSERT INTO chat_migrations (old_chat_id, new_chat_id, migrated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(old_chat_id) DO UPDATE SET
                        new_chat_id = excluded.new_chat_id,
                        migrated_at = excluded.migrated_at
                    """,
                    (old_id, new_id, now),
                )

            old_row = conn.execute(
                "SELECT id FROM droppers WHERE chat_id = ?", (old_id,)
            ).fetchone()
            new_row = conn.execute(
                "SELECT id FROM droppers WHERE chat_id = ?", (new_id,)
            ).fetchone()

            if old_row and not new_row:
                conn.execute(
                    "UPDATE droppers SET chat_id = ? WHERE chat_id = ?",
                    (new_id, old_id),
                )
                updated_dropper = True
            elif old_row and new_row:
                conn.execute(
                    "UPDATE droppers SET status = 'migrated_duplicate' WHERE chat_id = ?",
                    (old_id,),
                )
                logger.warning(
                    "Миграция chat_id: оба id уже в droppers old=%s new=%s",
                    old_id,
                    new_id,
                )

            conn.commit()

        logger.info(
            "Миграция chat_id: %s → %s (dropper_updated=%s)",
            old_id,
            new_id,
            updated_dropper,
        )
        return {
            "ok": True,
            "old": old_id,
            "new": new_id,
            "dropper_updated": updated_dropper,
        }

    def get_dropper_by_chat(self, chat_id: str) -> Dropper | None:
        raw = str(chat_id or "").strip()
        if not raw:
            return None
        candidates = []
        resolved = self.resolve_chat_id(raw)
        for key in (resolved, raw):
            if key and key not in candidates:
                candidates.append(key)

        with self._connect() as conn:
            for key in candidates:
                row = conn.execute(
                    "SELECT * FROM droppers WHERE chat_id = ?", (key,)
                ).fetchone()
                if row:
                    return self._row_dropper(row)
        return None

    def get_dropper_by_id(self, dropper_id: int) -> Dropper | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM droppers WHERE id = ?", (int(dropper_id),)
            ).fetchone()
        return self._row_dropper(row) if row else None

    def get_dropper_by_referral_code(
        self, code: str, *, only_enabled: bool = True
    ) -> Dropper | None:
        key = str(code or "").strip().upper()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM droppers WHERE upper(referral_code) = ?", (key,)
            ).fetchone()
        if not row:
            return None
        dropper = self._row_dropper(row)
        if only_enabled and not dropper.referral_program_enabled:
            return None
        return dropper

    def ensure_referral_code(self, dropper_id: int) -> str:
        """Згенерувати код якщо немає; існуючий не змінювати."""
        dropper = self.get_dropper_by_id(dropper_id)
        if not dropper:
            return ""
        if dropper.referral_code:
            return dropper.referral_code
        with self._connect() as conn:
            code = ""
            for _ in range(12):
                code = _gen_referral_code()
                try:
                    conn.execute(
                        "UPDATE droppers SET referral_code = ? WHERE id = ? AND (referral_code = '' OR referral_code IS NULL)",
                        (code, int(dropper_id)),
                    )
                    conn.commit()
                    break
                except sqlite3.IntegrityError:
                    continue
            row = conn.execute(
                "SELECT referral_code FROM droppers WHERE id = ?", (int(dropper_id),)
            ).fetchone()
        return str((row["referral_code"] if row else "") or code or "")

    def referral_fingerprint_taken(
        self,
        *,
        user_id: str = "",
        username: str = "",
        phone: str = "",
    ) -> dict[str, Any] | None:
        """Чи вже реєструвались з цими відбитками (антифрод рефералки)."""
        checks: list[tuple[str, str]] = []
        uid = str(user_id or "").strip()
        if uid:
            checks.append(("user_id", uid))
        uname = _norm_staff_username(username)
        if uname:
            checks.append(("username", uname))
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if len(digits) >= 10:
            checks.append(("phone", digits[-10:]))
        if not checks:
            return None
        with self._connect() as conn:
            for ftype, fval in checks:
                row = conn.execute(
                    """
                    SELECT * FROM referral_fingerprints
                    WHERE fingerprint_type = ? AND fingerprint_value = ?
                    """,
                    (ftype, fval),
                ).fetchone()
                if row:
                    return {
                        "type": row["fingerprint_type"],
                        "value": row["fingerprint_value"],
                        "first_dropper_id": row["first_dropper_id"],
                        "first_seen_at": row["first_seen_at"],
                    }
        return None

    def remember_referral_fingerprints(
        self,
        *,
        dropper_id: int,
        user_id: str = "",
        username: str = "",
        phone: str = "",
    ) -> None:
        now = _now()
        pairs: list[tuple[str, str]] = []
        uid = str(user_id or "").strip()
        if uid:
            pairs.append(("user_id", uid))
        uname = _norm_staff_username(username)
        if uname:
            pairs.append(("username", uname))
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if len(digits) >= 10:
            pairs.append(("phone", digits[-10:]))
        if not pairs:
            return
        with self._connect() as conn:
            for ftype, fval in pairs:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO referral_fingerprints (
                        fingerprint_type, fingerprint_value, first_dropper_id, first_seen_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (ftype, fval, int(dropper_id), now),
                )
            conn.commit()

    def list_referrals(self, dropper_id: int) -> list[Dropper]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM droppers
                WHERE referred_by_dropper_id = ?
                ORDER BY id DESC
                """,
                (int(dropper_id),),
            ).fetchall()
        return [self._row_dropper(r) for r in rows]

    def list_droppers(self) -> list[Dropper]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM droppers ORDER BY id DESC"
            ).fetchall()
        return [self._row_dropper(r) for r in rows]

    def create_dropper(
        self,
        chat_id: str,
        company_name: str,
        contact_name: str,
        phone: str,
        comment: str = "",
        registered_by_user_id: str = "",
        registered_by_username: str = "",
        require_full_payment: bool = False,
        referral_code_used: str = "",
        skip_referral_link: bool = False,
    ) -> Dropper:
        now = _now()
        referrer = (
            None
            if skip_referral_link
            else self.get_dropper_by_referral_code(referral_code_used)
        )
        referred_by = referrer.id if referrer else None
        referral_expires_at = (
            _add_months_iso(now, max(1, int(referrer.referral_months or 12)))
            if referrer
            else None
        )

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO droppers (
                    chat_id, company_name, contact_name, phone, comment,
                    require_full_payment, status,
                    registered_by_user_id, registered_by_username, created_at,
                    referral_code, referred_by_dropper_id, referral_expires_at,
                    referral_program_enabled, referral_months
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, '', ?, ?, 0, 12)
                """,
                (
                    str(chat_id).strip(),
                    company_name.strip(),
                    contact_name.strip(),
                    phone.strip(),
                    (comment or "").strip(),
                    1 if require_full_payment else 0,
                    str(registered_by_user_id or ""),
                    str(registered_by_username or ""),
                    now,
                    referred_by,
                    referral_expires_at,
                ),
            )
            dropper_id = int(cur.lastrowid)
            conn.commit()
            row = conn.execute(
                "SELECT * FROM droppers WHERE id = ?", (dropper_id,)
            ).fetchone()
        return self._row_dropper(row)

    def update_dropper_settings(
        self,
        chat_id: str,
        *,
        require_full_payment: bool | None = None,
        allow_cod: bool | None = None,
        allow_balance_payment: bool | None = None,
        allow_negative_balance: bool | None = None,
        negative_balance_limit: float | None = None,
        extra_discount_percent: float | None = None,
        orders_disabled: bool | None = None,
        referral_percent: float | None = None,
        referral_program_enabled: bool | None = None,
        referral_months: int | None = None,
        owner_comment: str | None = None,
        credit_holidays_days: int | None = None,
        notify_shipping_events: bool | None = None,
    ) -> Dropper | None:
        raw = str(chat_id).strip()
        key = self.resolve_chat_id(raw) or raw
        current = self.get_dropper_by_chat(key)
        if not current:
            return None

        fields: dict[str, Any] = {}
        if require_full_payment is not None:
            fields["require_full_payment"] = 1 if require_full_payment else 0
        if allow_cod is not None:
            fields["allow_cod"] = 1 if allow_cod else 0
        if allow_balance_payment is not None:
            fields["allow_balance_payment"] = 1 if allow_balance_payment else 0
        if allow_negative_balance is not None:
            fields["allow_negative_balance"] = 1 if allow_negative_balance else 0
        if negative_balance_limit is not None:
            fields["negative_balance_limit"] = max(0.0, float(negative_balance_limit))
        if extra_discount_percent is not None:
            fields["extra_discount_percent"] = max(
                0.0, min(100.0, float(extra_discount_percent))
            )
        if orders_disabled is not None:
            fields["orders_disabled"] = 1 if orders_disabled else 0
        if referral_percent is not None:
            fields["referral_percent"] = max(0.0, min(100.0, float(referral_percent)))
        if referral_months is not None:
            fields["referral_months"] = max(1, min(120, int(referral_months)))
        if referral_program_enabled is not None:
            fields["referral_program_enabled"] = 1 if referral_program_enabled else 0
        if owner_comment is not None:
            fields["owner_comment"] = str(owner_comment).strip()[:2000]
        if credit_holidays_days is not None:
            fields["credit_holidays_days"] = max(0, int(credit_holidays_days))
        if notify_shipping_events is not None:
            fields["notify_shipping_events"] = 1 if notify_shipping_events else 0

        if not fields:
            return current

        assignments = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [key]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE droppers SET {assignments} WHERE chat_id = ?",
                values,
            )
            if conn.total_changes == 0 and key != raw:
                conn.execute(
                    f"UPDATE droppers SET {assignments} WHERE chat_id = ?",
                    list(fields.values()) + [raw],
                )
            conn.commit()

        updated = self.get_dropper_by_chat(key)
        if (
            updated
            and referral_program_enabled is True
            and not (updated.referral_code or "").strip()
        ):
            self.ensure_referral_code(updated.id)
            updated = self.get_dropper_by_chat(key)
        return updated

    def delete_dropper(self, chat_id: str) -> bool:
        raw = str(chat_id).strip()
        key = self.resolve_chat_id(raw) or raw
        dropper = self.get_dropper_by_chat(key)
        if not dropper:
            return False
        with self._connect() as conn:
            conn.execute(
                "UPDATE droppers SET referred_by_dropper_id = NULL WHERE referred_by_dropper_id = ?",
                (dropper.id,),
            )
            conn.execute("DELETE FROM droppers WHERE id = ?", (dropper.id,))
            conn.commit()
        return True

    def dropper_turnover(self, dropper_id: int) -> float:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(total), 0) AS s
                FROM orders
                WHERE dropper_id = ? AND status != 'cancelled'
                """,
                (int(dropper_id),),
            ).fetchone()
        return float(row["s"] or 0)

    def update_credit_holidays_state(
        self,
        dropper_id: int,
        *,
        credit_debt_started_at: str | None | object = ...,
        credit_holidays_blocked: bool | None = None,
        credit_last_notified_at: str | None | object = ...,
    ) -> Dropper | None:
        fields: dict[str, Any] = {}
        if credit_debt_started_at is not ...:
            fields["credit_debt_started_at"] = credit_debt_started_at
        if credit_holidays_blocked is not None:
            fields["credit_holidays_blocked"] = 1 if credit_holidays_blocked else 0
        if credit_last_notified_at is not ...:
            fields["credit_last_notified_at"] = credit_last_notified_at
        if not fields:
            return self.get_dropper_by_id(dropper_id)
        assignments = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [int(dropper_id)]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE droppers SET {assignments} WHERE id = ?",
                values,
            )
            conn.commit()
        return self.get_dropper_by_id(dropper_id)

    def set_dropper_require_full_payment(
        self, chat_id: str, require_full_payment: bool
    ) -> Dropper | None:
        return self.update_dropper_settings(
            chat_id, require_full_payment=require_full_payment
        )

    def get_staff_by_user(self, telegram_user_id: str) -> StaffMember | None:
        return self.get_staff_by_identity(telegram_user_id=telegram_user_id)

    def get_staff_by_identity(
        self,
        telegram_user_id: str = "",
        username: str = "",
    ) -> StaffMember | None:
        uid = str(telegram_user_id or "").strip()
        uname = _norm_staff_username(username)
        with self._connect() as conn:
            if uid:
                row = conn.execute(
                    "SELECT * FROM staff WHERE telegram_user_id = ? AND active = 1",
                    (uid,),
                ).fetchone()
                if row:
                    return self._row_staff(row)
            if uname:
                rows = conn.execute(
                    "SELECT * FROM staff WHERE active = 1 AND username != ''"
                ).fetchall()
                for row in rows:
                    if _norm_staff_username(row["username"]) == uname:
                        return self._row_staff(row)
        return None

    def list_staff(self) -> list[StaffMember]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM staff ORDER BY id DESC"
            ).fetchall()
        return [self._row_staff(r) for r in rows]

    def upsert_staff(
        self,
        telegram_user_id: str,
        role: str,
        full_name: str = "",
        username: str = "",
        created_by_user_id: str = "",
    ) -> StaffMember:
        role = role.strip().lower()
        if role not in {"admin", "manager", "warehouse"}:
            raise ValueError("role must be admin, manager or warehouse")
        user_id = str(telegram_user_id).strip()
        now = _now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM staff WHERE telegram_user_id = ?", (user_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE staff
                    SET username = ?, full_name = ?, role = ?, active = 1,
                        created_by_user_id = COALESCE(NULLIF(?, ''), created_by_user_id)
                    WHERE telegram_user_id = ?
                    """,
                    (
                        username.strip(),
                        full_name.strip(),
                        role,
                        str(created_by_user_id or ""),
                        user_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO staff (
                        telegram_user_id, username, full_name, role, active,
                        created_at, created_by_user_id
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        username.strip(),
                        full_name.strip(),
                        role,
                        now,
                        str(created_by_user_id or ""),
                    ),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM staff WHERE telegram_user_id = ?", (user_id,)
            ).fetchone()
        return self._row_staff(row)

    def _row_ledger(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "dropper_id": row["dropper_id"],
            "amount": float(row["amount"] or 0),
            "entry_type": row["entry_type"],
            "title": row["title"] or "",
            "note": row["note"] or "",
            "related_order_id": row["related_order_id"] or "",
            "related_dropper_id": row["related_dropper_id"],
            "meta_json": row["meta_json"] or "",
            "created_at": row["created_at"],
        }

    def get_balance(self, dropper_id: int) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS bal FROM balance_ledger WHERE dropper_id = ?",
                (int(dropper_id),),
            ).fetchone()
        return float(row["bal"] or 0)

    def list_ledger(
        self,
        dropper_id: int | None = None,
        entry_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 500))
        sql = "SELECT * FROM balance_ledger WHERE 1=1"
        params: list[Any] = []
        if dropper_id is not None:
            sql += " AND dropper_id = ?"
            params.append(int(dropper_id))
        if entry_type:
            sql += " AND entry_type = ?"
            params.append(str(entry_type).strip())
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_ledger(r) for r in rows]

    def add_ledger_entry(
        self,
        *,
        dropper_id: int,
        amount: float,
        entry_type: str,
        title: str = "",
        note: str = "",
        related_order_id: str = "",
        related_dropper_id: int | None = None,
        meta_json: str = "",
    ) -> dict[str, Any] | None:
        now = _now()
        amount = float(amount)
        entry_type = str(entry_type or "").strip()
        related_order_id = str(related_order_id or "").strip()
        if not entry_type:
            raise ValueError("entry_type required")
        with self._connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO balance_ledger (
                        dropper_id, amount, entry_type, title, note,
                        related_order_id, related_dropper_id, meta_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(dropper_id),
                        amount,
                        entry_type,
                        (title or "").strip(),
                        (note or "").strip(),
                        related_order_id,
                        related_dropper_id,
                        meta_json or "",
                        now,
                    ),
                )
                entry_id = int(cur.lastrowid)
                conn.commit()
            except sqlite3.IntegrityError:
                # Ідемпотентність: повторне нарахування за той самий заказ
                row = conn.execute(
                    """
                    SELECT * FROM balance_ledger
                    WHERE dropper_id = ? AND entry_type = ? AND related_order_id = ?
                    """,
                    (int(dropper_id), entry_type, related_order_id),
                ).fetchone()
                return self._row_ledger(row) if row else None
            row = conn.execute(
                "SELECT * FROM balance_ledger WHERE id = ?", (entry_id,)
            ).fetchone()
        return self._row_ledger(row)

    def accrue_referral_from_drop_total(
        self,
        *,
        source_dropper_id: int,
        drop_total: float,
        order_id: str,
    ) -> dict[str, Any] | None:
        """
        Нарахування рефералу: % від дроп-суми замовлення
        на баланс дроппера, який запросив source.
        """
        source = self.get_dropper_by_id(source_dropper_id)
        if not source or not source.referred_by_dropper_id:
            return None
        referrer = self.get_dropper_by_id(source.referred_by_dropper_id)
        if (
            not referrer
            or not referrer.referral_program_enabled
            or float(referrer.referral_percent or 0) <= 0
        ):
            return None
        if source.referral_expires_at:
            expires = _parse_iso_dt(source.referral_expires_at)
            if expires and datetime.now(timezone.utc) > expires:
                return None
        total = float(drop_total or 0)
        if total <= 0:
            return None
        amount = round(total * float(referrer.referral_percent) / 100.0, 2)
        if amount <= 0:
            return None
        return self.add_ledger_entry(
            dropper_id=referrer.id,
            amount=amount,
            entry_type="referral_credit",
            title=f"Реферал від {source.company_name}",
            note=(
                f"{referrer.referral_percent}% від дроп-суми {total:.2f} ₴ "
                f"(заказ {order_id})"
            ),
            related_order_id=str(order_id).strip(),
            related_dropper_id=source.id,
            meta_json=(
                f'{{"drop_total":{total},"percent":{float(referrer.referral_percent)},'
                f'"source_dropper_id":{source.id}}}'
            ),
        )

    def list_dropper_balances(self) -> list[dict[str, Any]]:
        from bot.buyout import compute_buyout, tier_label

        droppers = self.list_droppers()
        items = []
        for d in droppers:
            bal = self.get_balance(d.id)
            referral_earned = sum(
                x["amount"]
                for x in self.list_ledger(d.id, entry_type="referral_credit", limit=5000)
            )
            orders = self.list_orders_for_dropper(d.id, limit=500)
            buyout = compute_buyout(orders)
            # Кешуємо актуальний % у дроппера (без нотифікацій)
            if (
                buyout["percent"] != d.buyout_percent
                or buyout["tier"] != (d.buyout_tier or "")
            ):
                self.update_buyout_state(
                    d.id,
                    buyout_percent=buyout["percent"],
                    buyout_tier=buyout["tier"],
                )
            items.append(
                {
                    "dropper": {
                        **d.to_dict(),
                        "buyout_percent": buyout["percent"],
                        "buyout_tier": buyout["tier"],
                    },
                    "balance": bal,
                    "referral_earned_total": round(float(referral_earned), 2),
                    "buyout": {
                        **buyout,
                        "label": tier_label(buyout["tier"], buyout["percent"]),
                    },
                }
            )
        return items

    def _row_order(self, row: sqlite3.Row) -> dict[str, Any]:
        import json

        payload: Any = {}
        raw = row["payload_json"] or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        return {
            "id": row["id"],
            "order_number": row["order_number"],
            "dropper_id": row["dropper_id"],
            "chat_id": row["chat_id"],
            "status": row["status"],
            "payment_method": row["payment_method"] or "",
            "delivery_method": row["delivery_method"] or "",
            "own_ttn": bool(row["own_ttn"]),
            "total": float(row["total"] or 0),
            "prepay": float(row["prepay"] or 0),
            "prepay_balance_debit": float(row["prepay_balance_debit"] or 0),
            "cod_amount": float(row["cod_amount"] or 0),
            "ttn_number": row["ttn_number"] or "",
            "ttn_status": row["ttn_status"] or "none",
            "sheets_sync_status": row["sheets_sync_status"] or "pending",
            "notify_dropper_status": row["notify_dropper_status"] or "pending",
            "payload": payload,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def next_order_number(self) -> str:
        day = datetime.now(timezone.utc).strftime("%y%m%d")
        prefix = f"K-{day}-"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT order_number FROM orders
                WHERE order_number LIKE ?
                ORDER BY id DESC LIMIT 1
                """,
                (f"{prefix}%",),
            ).fetchone()
        seq = 1
        if row:
            try:
                seq = int(str(row["order_number"]).rsplit("-", 1)[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:04d}"

    def create_order(
        self,
        *,
        dropper_id: int,
        chat_id: str,
        payment_method: str,
        delivery_method: str,
        own_ttn: bool,
        total: float,
        prepay: float,
        prepay_balance_debit: float,
        ttn_number: str,
        ttn_status: str,
        payload: dict[str, Any],
        cod_amount: float | None = None,
    ) -> dict[str, Any]:
        import json

        now = _now()
        order_number = self.next_order_number()
        total = max(0.0, float(total or 0))
        prepay = max(0.0, float(prepay or 0))
        debit = max(0.0, float(prepay_balance_debit or 0))
        if cod_amount is None:
            cod_amount = max(0.0, total - prepay)
        else:
            cod_amount = max(0.0, float(cod_amount or 0))
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO orders (
                    order_number, dropper_id, chat_id, status,
                    payment_method, delivery_method, own_ttn,
                    total, prepay, prepay_balance_debit, cod_amount,
                    ttn_number, ttn_status, sheets_sync_status,
                    notify_dropper_status, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending', ?, ?, ?)
                """,
                (
                    order_number,
                    int(dropper_id),
                    str(chat_id).strip(),
                    str(payment_method or "").strip(),
                    str(delivery_method or "").strip(),
                    1 if own_ttn else 0,
                    total,
                    prepay,
                    debit,
                    cod_amount,
                    str(ttn_number or "").strip(),
                    str(ttn_status or "none").strip(),
                    payload_json,
                    now,
                    now,
                ),
            )
            order_id = int(cur.lastrowid)
            conn.commit()
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return self._row_order(row)

    def update_order_flags(
        self,
        order_id: int,
        *,
        notify_dropper_status: str | None = None,
        ttn_status: str | None = None,
        sheets_sync_status: str | None = None,
        ttn_number: str | None = None,
    ) -> dict[str, Any] | None:
        fields: dict[str, Any] = {"updated_at": _now()}
        if notify_dropper_status is not None:
            fields["notify_dropper_status"] = notify_dropper_status
        if ttn_status is not None:
            fields["ttn_status"] = ttn_status
        if sheets_sync_status is not None:
            fields["sheets_sync_status"] = sheets_sync_status
        if ttn_number is not None:
            fields["ttn_number"] = ttn_number
        if len(fields) == 1:
            return self.get_order(order_id)
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [int(order_id)]
        with self._connect() as conn:
            conn.execute(f"UPDATE orders SET {sets} WHERE id = ?", values)
            conn.commit()
        return self.get_order(order_id)

    def merge_order_payload(
        self, order_id: int, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        import json

        order = self.get_order(order_id)
        if not order:
            return None
        payload = dict(order.get("payload") or {})
        for key, value in (patch or {}).items():
            payload[key] = value
        with self._connect() as conn:
            conn.execute(
                "UPDATE orders SET payload_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False), _now(), int(order_id)),
            )
            conn.commit()
        return self.get_order(order_id)

    def list_orders_pending_ttn_create(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE own_ttn = 0
                  AND (ttn_number IS NULL OR ttn_number = '')
                  AND ttn_status IN ('pending_create', 'create_error', 'none')
                  AND status != 'cancelled'
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_order(r) for r in rows]

    def list_orders_for_tracking(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 300))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE ttn_number IS NOT NULL AND ttn_number != ''
                  AND ttn_status NOT IN (
                    'received', 'returned', 'refused', 'failed', 'cancelled',
                    'provided', 'return_at_warehouse'
                  )
                  AND status != 'cancelled'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_order(r) for r in rows]

    def list_orders_at_warehouse(self, limit: int = 500) -> list[dict[str, Any]]:
        """Замовлення, що зараз лежать на відділенні (для нагадувань 5/7 день)."""
        limit = max(1, min(int(limit or 500), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE ttn_status = 'at_warehouse'
                  AND ttn_number IS NOT NULL AND ttn_number != ''
                  AND status != 'cancelled'
                  AND own_ttn = 0
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_order(r) for r in rows]

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE id = ?", (int(order_id),)
            ).fetchone()
        return self._row_order(row) if row else None

    def get_order_by_ttn(self, ttn_number: str) -> dict[str, Any] | None:
        import re

        key = re.sub(r"\s+", "", str(ttn_number or "").strip())
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE ttn_number = ? ORDER BY id DESC LIMIT 1",
                (key,),
            ).fetchone()
        return self._row_order(row) if row else None

    def get_order_by_number(self, order_number: str) -> dict[str, Any] | None:
        key = str(order_number or "").strip()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_number = ?", (key,)
            ).fetchone()
        return self._row_order(row) if row else None

    def list_orders_for_dropper(
        self, dropper_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE dropper_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(dropper_id), limit),
            ).fetchall()
        return [self._row_order(r) for r in rows]

    @staticmethod
    def normalize_client_phone(raw: str) -> str:
        """Нормалізація телефону клієнта → 380XXXXXXXXX (12 цифр) або ''."""
        import re

        digits = re.sub(r"\D", "", str(raw or ""))
        if not digits:
            return ""
        if digits.startswith("380"):
            body = digits[3:]
            if len(body) >= 9:
                return "380" + body[-9:]
            return ""
        if digits.startswith("0") and len(digits) >= 10:
            return "380" + digits[1:10]
        if len(digits) >= 9:
            return "380" + digits[-9:]
        return ""

    def update_buyout_state(
        self,
        dropper_id: int,
        *,
        buyout_percent: float | None | object = ...,
        buyout_tier: str | None = None,
        buyout_tier_notified: str | None = None,
        buyout_half_warned: bool | None = None,
    ) -> Dropper | None:
        fields: dict[str, Any] = {}
        if buyout_percent is not ...:
            fields["buyout_percent"] = (
                None if buyout_percent is None else float(buyout_percent)  # type: ignore[arg-type]
            )
        if buyout_tier is not None:
            fields["buyout_tier"] = str(buyout_tier or "")
        if buyout_tier_notified is not None:
            fields["buyout_tier_notified"] = str(buyout_tier_notified or "")
        if buyout_half_warned is not None:
            fields["buyout_half_warned"] = 1 if buyout_half_warned else 0
        if not fields:
            return self.get_dropper_by_id(dropper_id)
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [int(dropper_id)]
        with self._connect() as conn:
            conn.execute(f"UPDATE droppers SET {sets} WHERE id = ?", values)
            conn.commit()
        return self.get_dropper_by_id(dropper_id)

    def list_phone_blacklist(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM phone_blacklist
                ORDER BY id DESC
                """
            ).fetchall()
        return [
            {
                "id": r["id"],
                "phone_digits": r["phone_digits"],
                "phone_display": r["phone_display"] or r["phone_digits"],
                "note": r["note"] or "",
                "created_at": r["created_at"],
                "created_by_user_id": r["created_by_user_id"] or "",
            }
            for r in rows
        ]

    def add_phone_blacklist(
        self,
        phone: str,
        *,
        note: str = "",
        created_by_user_id: str = "",
    ) -> dict[str, Any]:
        digits = self.normalize_client_phone(phone)
        if len(digits) < 12:
            raise ValueError("Вкажіть повний номер телефону (+380…)")
        display = f"+{digits}"
        now = _now()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO phone_blacklist (
                        phone_digits, phone_display, note, created_at, created_by_user_id
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        digits,
                        display,
                        str(note or "").strip()[:500],
                        now,
                        str(created_by_user_id or "").strip()[:64],
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("Цей номер уже в чорному списку") from exc
            row = conn.execute(
                "SELECT * FROM phone_blacklist WHERE phone_digits = ?", (digits,)
            ).fetchone()
        return {
            "id": row["id"],
            "phone_digits": row["phone_digits"],
            "phone_display": row["phone_display"],
            "note": row["note"] or "",
            "created_at": row["created_at"],
            "created_by_user_id": row["created_by_user_id"] or "",
        }

    def remove_phone_blacklist(self, entry_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM phone_blacklist WHERE id = ?", (int(entry_id),)
            )
            conn.commit()
            return cur.rowcount > 0

    def is_phone_blacklisted(self, phone: str) -> bool:
        digits = self.normalize_client_phone(phone)
        if not digits:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM phone_blacklist WHERE phone_digits = ? LIMIT 1",
                (digits,),
            ).fetchone()
        return bool(row)

    def default_general_settings(self) -> dict[str, Any]:
        return {
            "np_api_keys": [],
            "payment_requisites": [],
            "sender_city": {
                "label": "",
                "city_ref": "",
                "settlement_ref": "",
            },
            "sender_warehouse": {
                "label": "",
                "ref": "",
                "number": "",
            },
            "parcel_defaults": {
                "weight_kg": 0.5,
                "length_cm": 30,
                "width_cm": 20,
                "height_cm": 10,
                "seats_amount": 1,
                "description": "Товар",
            },
            "orders_spreadsheet_id": "1RYNXnGbXdB0ve7pBy4KD-SdaKAaoLipiKC9vOeGfczE",
            "orders_spreadsheet_url": (
                "https://docs.google.com/spreadsheets/d/"
                "1RYNXnGbXdB0ve7pBy4KD-SdaKAaoLipiKC9vOeGfczE/edit"
            ),
            "orders_sheet_title": "Заказы",
        }

    @staticmethod
    def _normalize_payment_requisite(item: Any) -> dict[str, Any] | None:
        import uuid

        if not isinstance(item, dict):
            return None
        kind = str(item.get("kind") or item.get("type") or "fop").strip().lower()
        if kind not in ("fop", "card"):
            kind = "fop"
        label = str(item.get("label") or "").strip()
        if not label:
            label = "ФОП / рахунок" if kind == "fop" else "Картка"
        enabled = bool(item.get("enabled"))
        recipient = str(item.get("recipient") or "").strip()[:200]
        edrpou = str(item.get("edrpou") or "").strip()[:20]
        iban = str(item.get("iban") or "").strip()[:40]
        card_number = str(item.get("card_number") or "").strip()[:32]
        bank = str(item.get("bank") or "").strip()[:120]
        purpose = str(item.get("purpose") or "").strip()[:300]
        rid = str(item.get("id") or "").strip() or uuid.uuid4().hex[:10]
        has_data = bool(recipient or edrpou or iban or card_number or bank or purpose)
        if not has_data and not enabled and not str(item.get("label") or "").strip():
            return None
        return {
            "id": rid,
            "kind": kind,
            "label": label[:80],
            "enabled": enabled,
            "recipient": recipient,
            "edrpou": edrpou,
            "iban": iban,
            "card_number": card_number,
            "bank": bank,
            "purpose": purpose,
        }

    def get_general_settings(self) -> dict[str, Any]:
        import json

        defaults = self.default_general_settings()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                ("general",),
            ).fetchone()
        if not row:
            return defaults
        try:
            data = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            return defaults
        if not isinstance(data, dict):
            return defaults
        merged = {**defaults, **data}
        # nested defaults
        for key in ("sender_city", "sender_warehouse", "parcel_defaults"):
            base = defaults.get(key) or {}
            cur = data.get(key) if isinstance(data.get(key), dict) else {}
            merged[key] = {**base, **cur}
        if not isinstance(merged.get("np_api_keys"), list):
            merged["np_api_keys"] = []
        raw_req = merged.get("payment_requisites")
        if not isinstance(raw_req, list):
            merged["payment_requisites"] = []
        else:
            merged["payment_requisites"] = [
                row
                for row in (self._normalize_payment_requisite(x) for x in raw_req)
                if row
            ]
        return merged

    def save_general_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        import json
        import re
        import uuid

        current = self.get_general_settings()
        keys_in = payload.get("np_api_keys")
        np_keys: list[dict[str, Any]] = []
        if isinstance(keys_in, list):
            for item in keys_in:
                if not isinstance(item, dict):
                    continue
                api_key = str(item.get("api_key") or "").strip()
                label = str(item.get("label") or "").strip() or "Кабінет НП"
                enabled = bool(item.get("enabled"))
                kid = str(item.get("id") or "").strip() or uuid.uuid4().hex[:10]
                if not api_key and not enabled:
                    # порожній рядок без ключа — пропускаємо
                    continue
                np_keys.append(
                    {
                        "id": kid,
                        "label": label[:80],
                        "api_key": api_key[:128],
                        "enabled": enabled,
                    }
                )

        if "payment_requisites" in payload:
            req_in = payload.get("payment_requisites")
            payment_requisites: list[dict[str, Any]] = []
            if isinstance(req_in, list):
                for item in req_in:
                    row = self._normalize_payment_requisite(item)
                    if row:
                        payment_requisites.append(row)
        else:
            payment_requisites = list(current.get("payment_requisites") or [])

        city_in = payload.get("sender_city") if isinstance(payload.get("sender_city"), dict) else {}
        wh_in = (
            payload.get("sender_warehouse")
            if isinstance(payload.get("sender_warehouse"), dict)
            else {}
        )
        parcel_in = (
            payload.get("parcel_defaults")
            if isinstance(payload.get("parcel_defaults"), dict)
            else {}
        )

        def _num(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return float(default)

        sheet_url = str(
            payload.get("orders_spreadsheet_url")
            or current.get("orders_spreadsheet_url")
            or ""
        ).strip()
        sheet_id = str(payload.get("orders_spreadsheet_id") or "").strip()
        if not sheet_id and sheet_url:
            m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
            if m:
                sheet_id = m.group(1)
        if not sheet_id:
            sheet_id = str(current.get("orders_spreadsheet_id") or "")

        saved = {
            "np_api_keys": np_keys,
            "payment_requisites": payment_requisites,
            "sender_city": {
                "label": str(city_in.get("label") or "").strip()[:200],
                "city_ref": str(city_in.get("city_ref") or "").strip()[:64],
                "settlement_ref": str(city_in.get("settlement_ref") or "").strip()[:64],
            },
            "sender_warehouse": {
                "label": str(wh_in.get("label") or "").strip()[:300],
                "ref": str(wh_in.get("ref") or "").strip()[:64],
                "number": str(wh_in.get("number") or "").strip()[:32],
            },
            "parcel_defaults": {
                "weight_kg": max(0.1, _num(parcel_in.get("weight_kg"), 0.5)),
                "length_cm": max(1.0, _num(parcel_in.get("length_cm"), 30)),
                "width_cm": max(1.0, _num(parcel_in.get("width_cm"), 20)),
                "height_cm": max(1.0, _num(parcel_in.get("height_cm"), 10)),
                "seats_amount": max(1, int(_num(parcel_in.get("seats_amount"), 1))),
                "description": str(parcel_in.get("description") or "Товар").strip()[:120]
                or "Товар",
            },
            "orders_spreadsheet_id": sheet_id[:128],
            "orders_spreadsheet_url": sheet_url[:500],
            "orders_sheet_title": str(
                payload.get("orders_sheet_title")
                or current.get("orders_sheet_title")
                or "Заказы"
            ).strip()[:80]
            or "Заказы",
        }
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                ("general", json.dumps(saved, ensure_ascii=False), now),
            )
            conn.commit()
        return saved

    def get_enabled_np_api_keys(self) -> list[dict[str, Any]]:
        settings = self.get_general_settings()
        keys = settings.get("np_api_keys") or []
        return [
            k
            for k in keys
            if isinstance(k, dict) and k.get("enabled") and str(k.get("api_key") or "").strip()
        ]

    def get_enabled_payment_requisites(self) -> list[dict[str, Any]]:
        """Лише реквізити з галочкою — те, що бачать дроппери."""
        settings = self.get_general_settings()
        rows = settings.get("payment_requisites") or []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("enabled"):
                continue
            kind = str(row.get("kind") or "fop").strip().lower()
            if kind not in ("fop", "card"):
                kind = "fop"
            out.append(
                {
                    "id": str(row.get("id") or ""),
                    "kind": kind,
                    "label": str(row.get("label") or "").strip(),
                    "recipient": str(row.get("recipient") or "").strip(),
                    "edrpou": str(row.get("edrpou") or "").strip(),
                    "iban": str(row.get("iban") or "").strip(),
                    "card_number": str(row.get("card_number") or "").strip(),
                    "bank": str(row.get("bank") or "").strip(),
                    "purpose": str(row.get("purpose") or "").strip(),
                }
            )
        return out

    def get_np_api_keys_for_rotation(self) -> list[dict[str, Any]]:
        """
        Порядок спроб: спочатку ключі з галочкою (основні), потім без галочки (резерв).
        """
        settings = self.get_general_settings()
        keys = settings.get("np_api_keys") or []
        with_key: list[dict[str, Any]] = [
            k
            for k in keys
            if isinstance(k, dict) and str(k.get("api_key") or "").strip()
        ]
        primary = [k for k in with_key if k.get("enabled")]
        backup = [k for k in with_key if not k.get("enabled")]
        return primary + backup
