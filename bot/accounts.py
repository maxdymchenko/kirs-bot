"""SQLite: дропперы, сотрудники, миграции chat_id."""

from __future__ import annotations

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


@dataclass
class Dropper:
    id: int
    chat_id: str
    company_name: str
    contact_name: str
    phone: str
    comment: str
    require_full_payment: bool
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
    referral_code: str
    referred_by_dropper_id: int | None
    referral_percent: float
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
            "referral_code": self.referral_code,
            "referred_by_dropper_id": self.referred_by_dropper_id,
            "referral_percent": self.referral_percent,
            "status": self.status,
            "registered_by_user_id": self.registered_by_user_id,
            "registered_by_username": self.registered_by_username,
            "created_at": self.created_at,
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Без owner_comment — для відповідей дропперу."""
        data = self.to_dict()
        data.pop("owner_comment", None)
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
                ("referral_code", "referral_code TEXT NOT NULL DEFAULT ''"),
                ("referred_by_dropper_id", "referred_by_dropper_id INTEGER"),
                ("referral_percent", "referral_percent REAL NOT NULL DEFAULT 0"),
                ("owner_comment", "owner_comment TEXT NOT NULL DEFAULT ''"),
                ("credit_holidays_days", "credit_holidays_days INTEGER NOT NULL DEFAULT 0"),
                ("credit_debt_started_at", "credit_debt_started_at TEXT"),
                ("credit_holidays_blocked", "credit_holidays_blocked INTEGER NOT NULL DEFAULT 0"),
                ("credit_last_notified_at", "credit_last_notified_at TEXT"),
            ):
                self._ensure_column(conn, "droppers", column, ddl)

            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_droppers_referral_code
                ON droppers(referral_code)
                WHERE referral_code != ''
                """
            )

            # Згенерувати referral_code для старих записів
            rows = conn.execute(
                "SELECT id FROM droppers WHERE referral_code IS NULL OR referral_code = ''"
            ).fetchall()
            for row in rows:
                for _ in range(8):
                    code = _gen_referral_code()
                    try:
                        conn.execute(
                            "UPDATE droppers SET referral_code = ? WHERE id = ?",
                            (code, row["id"]),
                        )
                        break
                    except sqlite3.IntegrityError:
                        continue

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
            referral_code=str(self._row_get(row, "referral_code", "") or ""),
            referred_by_dropper_id=int(ref_by) if ref_by not in (None, "") else None,
            referral_percent=float(self._row_get(row, "referral_percent", 0) or 0),
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

    def get_dropper_by_referral_code(self, code: str) -> Dropper | None:
        key = str(code or "").strip().upper()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM droppers WHERE upper(referral_code) = ?", (key,)
            ).fetchone()
        return self._row_dropper(row) if row else None

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
    ) -> Dropper:
        now = _now()
        referrer = self.get_dropper_by_referral_code(referral_code_used)
        referred_by = referrer.id if referrer else None

        with self._connect() as conn:
            dropper_id = None
            code = ""
            for _ in range(10):
                code = _gen_referral_code()
                try:
                    cur = conn.execute(
                        """
                        INSERT INTO droppers (
                            chat_id, company_name, contact_name, phone, comment,
                            require_full_payment, status,
                            registered_by_user_id, registered_by_username, created_at,
                            referral_code, referred_by_dropper_id
                        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
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
                            code,
                            referred_by,
                        ),
                    )
                    dropper_id = int(cur.lastrowid)
                    break
                except sqlite3.IntegrityError as exc:
                    if "referral_code" in str(exc).lower():
                        continue
                    raise
            if dropper_id is None:
                raise RuntimeError("Не вдалося створити referral_code")
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
        allow_balance_payment: bool | None = None,
        allow_negative_balance: bool | None = None,
        negative_balance_limit: float | None = None,
        extra_discount_percent: float | None = None,
        orders_disabled: bool | None = None,
        referral_percent: float | None = None,
        owner_comment: str | None = None,
        credit_holidays_days: int | None = None,
    ) -> Dropper | None:
        raw = str(chat_id).strip()
        key = self.resolve_chat_id(raw) or raw
        current = self.get_dropper_by_chat(key)
        if not current:
            return None

        fields: dict[str, Any] = {}
        if require_full_payment is not None:
            fields["require_full_payment"] = 1 if require_full_payment else 0
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
        if owner_comment is not None:
            fields["owner_comment"] = str(owner_comment).strip()[:2000]
        if credit_holidays_days is not None:
            fields["credit_holidays_days"] = max(0, int(credit_holidays_days))

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
        return self.get_dropper_by_chat(key)

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
        key = str(telegram_user_id or "").strip()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM staff WHERE telegram_user_id = ? AND active = 1",
                (key,),
            ).fetchone()
        return self._row_staff(row) if row else None

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
        if not referrer or float(referrer.referral_percent or 0) <= 0:
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
        droppers = self.list_droppers()
        items = []
        for d in droppers:
            bal = self.get_balance(d.id)
            refs = self.list_ledger(d.id, entry_type="referral_credit", limit=5)
            referral_earned = sum(x["amount"] for x in self.list_ledger(d.id, entry_type="referral_credit", limit=5000))
            items.append(
                {
                    "dropper": d.to_dict(),
                    "balance": bal,
                    "referral_earned_total": round(float(referral_earned), 2),
                    "recent_referrals": refs,
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

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE id = ?", (int(order_id),)
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
        limit = max(1, min(int(limit or 50), 200))
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

    def default_general_settings(self) -> dict[str, Any]:
        return {
            "np_api_keys": [],
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
