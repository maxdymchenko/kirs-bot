import re
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import Message

from bs4 import BeautifulSoup

IGNORE_EMAIL_DOMAINS = ("olx.", "noreply", "no-reply", "mailer", "notification")

DEFAULT_ALLOWED_LINK_PATHS = (
    "/myaccount/answer/",
    "/myaccount/answers/",
    "/myaccount/safedealorders/",
)


@dataclass
class ParsedEmail:
    uid: str
    subject: str
    account_email: str
    chat_link: str
    raw_from: str


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_text_from_message(msg: Message) -> str:
    texts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                soup = BeautifulSoup(text, "lxml")
                for link in soup.find_all("a", href=True):
                    texts.append(link["href"])
                texts.append(soup.get_text(" ", strip=True))
            elif content_type == "text/plain":
                texts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                soup = BeautifulSoup(text, "lxml")
                for link in soup.find_all("a", href=True):
                    texts.append(link["href"])
                texts.append(soup.get_text(" ", strip=True))
            else:
                texts.append(text)

    return "\n".join(texts)


def _is_ignored_email(email: str) -> bool:
    lower = email.lower()
    return any(marker in lower for marker in IGNORE_EMAIL_DOMAINS)


def _subject_allowed(subject: str, allowed_subjects: list[str]) -> bool:
    if not allowed_subjects:
        return True
    subject_lower = subject.lower()
    return any(item.lower() in subject_lower for item in allowed_subjects)


def _sender_allowed(raw_from: str, required_sender: str) -> bool:
    if not required_sender:
        return True
    return required_sender.lower() in raw_from.lower()


def _link_matches_allowed_paths(link: str, allowed_paths: list[str]) -> bool:
    lower = link.lower()
    return any(path.lower() in lower for path in allowed_paths)


def _find_chat_link(
    text: str,
    pattern: str,
    allowed_paths: list[str] | None = None,
) -> str:
    allowed_paths = allowed_paths or list(DEFAULT_ALLOWED_LINK_PATHS)
    links = re.findall(pattern, text, flags=re.IGNORECASE)
    valid = [
        link.rstrip(".,;)")
        for link in links
        if _link_matches_allowed_paths(link, allowed_paths)
    ]
    if not valid:
        return ""

    priorities = (
        lambda link: "/myaccount/answer/" in link.lower() and "my_chat" in link.lower(),
        lambda link: "/myaccount/answer/" in link.lower(),
        lambda link: "/myaccount/answers/" in link.lower(),
        lambda link: "/myaccount/safedealorders/" in link.lower(),
    )
    for matcher in priorities:
        for link in valid:
            if matcher(link):
                return link

    return valid[0]


def _find_account_email(text: str, pattern: str, fallback_headers: list[str]) -> str:
    candidates = re.findall(pattern, text, flags=re.IGNORECASE)
    candidates = [e for e in candidates if not _is_ignored_email(e)]

    account_context = re.findall(
        r"(?:konto|account|аккаунт|adres(?:\s+e-?mail)?|e-?mail|почт[аи]|"
        r"на\s+(?:почту|email)|для\s+(?:почты|email)|"
        r"wiadomość\s+dla|message\s+for)\s*[:\-]?\s*"
        r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        text,
        flags=re.IGNORECASE,
    )
    if account_context:
        return account_context[0]

    if candidates:
        return candidates[0]

    for header_value in fallback_headers:
        header_emails = re.findall(pattern, header_value, flags=re.IGNORECASE)
        header_emails = [e for e in header_emails if not _is_ignored_email(e)]
        if header_emails:
            return header_emails[0]

    return "не определён"


def parse_email(
    raw_email: bytes,
    uid: str,
    patterns: dict[str, str],
    allowed_subjects: list[str] | None = None,
    required_sender: str = "",
    allowed_link_paths: list[str] | None = None,
) -> ParsedEmail | None:
    msg = message_from_bytes(raw_email)

    subject = _decode_header_value(msg.get("Subject"))
    raw_from = _decode_header_value(msg.get("From"))

    if not _subject_allowed(subject, allowed_subjects or []):
        return None
    if not _sender_allowed(raw_from, required_sender):
        return None

    body_text = _extract_text_from_message(msg)

    header_values = [
        _decode_header_value(msg.get("To")),
        _decode_header_value(msg.get("Delivered-To")),
        _decode_header_value(msg.get("X-Original-To")),
        _decode_header_value(msg.get("X-Forwarded-To")),
        _decode_header_value(msg.get("Envelope-To")),
    ]

    chat_link = _find_chat_link(
        body_text,
        patterns["chat_link"],
        allowed_link_paths,
    )
    account_email = _find_account_email(
        body_text,
        patterns["account_email"],
        header_values,
    )

    if not chat_link:
        return None

    return ParsedEmail(
        uid=uid,
        subject=subject,
        account_email=account_email,
        chat_link=chat_link,
        raw_from=raw_from,
    )
