import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Notification:
    id: int
    anchor_id: str
    email_uid: str
    account_email: str
    chat_link: str
    subject: str
    message_text: str
    telegram_message_id: int | None
    telegram_chat_id: str
    processed: bool
    processed_at: str | None
    processed_by: str | None
    created_at: str


class NotificationStorage:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or Path(__file__).resolve().parent.parent / "data" / "notifications.db")
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
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_uid TEXT NOT NULL,
                    account_email TEXT NOT NULL,
                    chat_link TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    telegram_message_id INTEGER,
                    telegram_chat_id TEXT NOT NULL,
                    processed INTEGER NOT NULL DEFAULT 0,
                    processed_at TEXT,
                    processed_by TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_email_uid
                ON notifications(email_uid)
                """
            )

    @staticmethod
    def format_anchor(notification_id: int) -> str:
        return f"{notification_id:04d}"

    def create(
        self,
        email_uid: str,
        account_email: str,
        chat_link: str,
        subject: str,
        message_text: str,
        telegram_chat_id: str,
    ) -> Notification:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notifications (
                    email_uid, account_email, chat_link, subject, message_text,
                    telegram_chat_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (email_uid, account_email, chat_link, subject, message_text, telegram_chat_id, now),
            )
            notification_id = cursor.lastrowid
            conn.commit()
        return self.get(notification_id)

    def get(self, notification_id: int) -> Notification | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
        return self._row_to_notification(row) if row else None

    def get_by_email_uid(self, email_uid: str) -> Notification | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE email_uid = ?",
                (email_uid,),
            ).fetchone()
        return self._row_to_notification(row) if row else None

    def set_telegram_message_id(self, notification_id: int, message_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE notifications SET telegram_message_id = ? WHERE id = ?",
                (message_id, notification_id),
            )
            conn.commit()

    def update_message_text(self, notification_id: int, message_text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE notifications SET message_text = ? WHERE id = ?",
                (message_text, notification_id),
            )
            conn.commit()

    def delete(self, notification_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            conn.commit()

    def mark_processed(self, notification_id: int, processed_by: str) -> Notification | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notifications
                SET processed = 1, processed_at = ?, processed_by = ?
                WHERE id = ?
                """,
                (now, processed_by, notification_id),
            )
            conn.commit()
        return self.get(notification_id)

    def list_unprocessed(self, limit: int = 50) -> list[Notification]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notifications
                WHERE processed = 0
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def _row_to_notification(self, row: sqlite3.Row) -> Notification:
        notification_id = row["id"]
        return Notification(
            id=notification_id,
            anchor_id=self.format_anchor(notification_id),
            email_uid=row["email_uid"],
            account_email=row["account_email"],
            chat_link=row["chat_link"],
            subject=row["subject"],
            message_text=row["message_text"],
            telegram_message_id=row["telegram_message_id"],
            telegram_chat_id=row["telegram_chat_id"],
            processed=bool(row["processed"]),
            processed_at=row["processed_at"],
            processed_by=row["processed_by"],
            created_at=row["created_at"],
        )
