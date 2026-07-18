"""SQLite: дропперы, сотрудники, сессии ролей."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Dropper:
    id: int
    chat_id: str
    company_name: str
    contact_name: str
    phone: str
    comment: str
    require_full_payment: bool
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
            "status": self.status,
            "registered_by_user_id": self.registered_by_user_id,
            "registered_by_username": self.registered_by_username,
            "created_at": self.created_at,
        }


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
        self.db_path = Path(
            db_path
            or Path(__file__).resolve().parent.parent / "data" / "app.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            conn.commit()

    def _row_dropper(self, row: sqlite3.Row) -> Dropper:
        return Dropper(
            id=row["id"],
            chat_id=row["chat_id"],
            company_name=row["company_name"],
            contact_name=row["contact_name"],
            phone=row["phone"],
            comment=row["comment"] or "",
            require_full_payment=bool(row["require_full_payment"]),
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

    def get_dropper_by_chat(self, chat_id: str) -> Dropper | None:
        key = str(chat_id or "").strip()
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM droppers WHERE chat_id = ?", (key,)
            ).fetchone()
        return self._row_dropper(row) if row else None

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
    ) -> Dropper:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO droppers (
                    chat_id, company_name, contact_name, phone, comment,
                    require_full_payment, status,
                    registered_by_user_id, registered_by_username, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
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
                ),
            )
            dropper_id = int(cur.lastrowid)
            conn.commit()
            row = conn.execute(
                "SELECT * FROM droppers WHERE id = ?", (dropper_id,)
            ).fetchone()
        return self._row_dropper(row)

    def set_dropper_require_full_payment(
        self, chat_id: str, require_full_payment: bool
    ) -> Dropper | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE droppers
                SET require_full_payment = ?
                WHERE chat_id = ?
                """,
                (1 if require_full_payment else 0, str(chat_id).strip()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM droppers WHERE chat_id = ?",
                (str(chat_id).strip(),),
            ).fetchone()
        return self._row_dropper(row) if row else None

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
        if role not in {"manager", "warehouse"}:
            raise ValueError("role must be manager or warehouse")
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
