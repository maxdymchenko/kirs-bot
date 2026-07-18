"""SQLite: дропперы, сотрудники, миграции chat_id."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.paths import app_db_path

logger = logging.getLogger(__name__)


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
        self.db_path = Path(db_path or app_db_path())
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

    def resolve_chat_id(self, chat_id: str | int | None) -> str:
        """Вернуть актуальный chat_id с учётом миграций group → supergroup."""
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
        """
        Переписать все ссылки со старого chat_id на новый.
        Безопасно при повторном вызове (идемпотентно).
        """
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
            if existing and str(existing["new_chat_id"]) == new_id:
                # Уже записано — всё равно убедимся, что dropper на новом id
                pass
            else:
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
                # Конфликт крайне редкий: оставляем запись на new_id, старую деактивируем
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
        raw = str(chat_id).strip()
        key = self.resolve_chat_id(raw) or raw
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE droppers
                SET require_full_payment = ?
                WHERE chat_id = ?
                """,
                (1 if require_full_payment else 0, key),
            )
            if cur.rowcount == 0 and key != raw:
                conn.execute(
                    """
                    UPDATE droppers
                    SET require_full_payment = ?
                    WHERE chat_id = ?
                    """,
                    (1 if require_full_payment else 0, raw),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM droppers WHERE chat_id = ?",
                (key,),
            ).fetchone()
            if not row and key != raw:
                row = conn.execute(
                    "SELECT * FROM droppers WHERE chat_id = ?",
                    (raw,),
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
