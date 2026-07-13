import imaplib
import logging
from email import message_from_bytes
from typing import Any

from modules.email_olx.parser import ParsedEmail, parse_email

logger = logging.getLogger(__name__)


class ImapClient:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        folder: str = "INBOX",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder
        self._connection: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        self._connection = imaplib.IMAP4_SSL(self.host, self.port)
        self._connection.login(self.user, self.password)
        status, _ = self._connection.select(self.folder)
        if status != "OK":
            raise ConnectionError(f"Не удалось открыть папку {self.folder}")

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def _build_search_criteria(
        self,
        only_unseen: bool,
        sender_filter: str,
        subject_filter: str,
    ) -> str:
        criteria: list[str] = []
        if only_unseen:
            criteria.append("UNSEEN")
        if sender_filter:
            criteria.append(f'FROM "{sender_filter}"')
        if subject_filter:
            criteria.append(f'SUBJECT "{subject_filter}"')
        return f"({' '.join(criteria)})" if criteria else "ALL"

    def fetch_new_emails(
        self,
        only_unseen: bool = True,
        sender_filter: str = "",
        subject_filter: str = "",
        patterns: dict[str, str] | None = None,
        allowed_subjects: list[str] | None = None,
        required_sender: str = "",
        allowed_link_paths: list[str] | None = None,
    ) -> list[ParsedEmail]:
        if not self._connection:
            raise RuntimeError("IMAP не подключён")

        patterns = patterns or {}
        search_query = self._build_search_criteria(only_unseen, sender_filter, subject_filter)
        status, data = self._connection.search(None, search_query)
        if status != "OK":
            logger.warning("Ошибка поиска писем: %s", status)
            return []

        email_ids = data[0].split()
        results: list[ParsedEmail] = []

        for email_id in email_ids:
            uid = email_id.decode()
            status, msg_data = self._connection.fetch(email_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            if not isinstance(raw_email, bytes):
                continue

            parsed = parse_email(
                raw_email,
                uid,
                patterns,
                allowed_subjects=allowed_subjects,
                required_sender=required_sender or sender_filter,
                allowed_link_paths=allowed_link_paths,
            )
            if parsed:
                results.append(parsed)
            else:
                msg = message_from_bytes(raw_email)
                subject = msg.get("Subject", "")
                logger.debug("Письмо пропущено (не подходит под фильтры OLX): %s", subject)

        return results

    def mark_as_read(self, uids: list[str]) -> None:
        if not self._connection or not uids:
            return
        for uid in uids:
            self._connection.store(uid.encode(), "+FLAGS", "\\Seen")
