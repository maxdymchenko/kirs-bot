"""Определение роли по chat_id / user_id."""

from __future__ import annotations

from bot.accounts import AppStorage, Dropper, StaffMember
from bot.core import Settings


def _norm(value: str | int | None) -> str:
    return str(value or "").strip()


def _ids_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    # На случай записи без минуса / с минусом
    return a.lstrip("-") == b.lstrip("-") and (a.startswith("-") or b.startswith("-"))


def is_owner_user(settings: Settings, user_id: str | int | None) -> bool:
    current = _norm(user_id)
    if not current:
        return False
    allowed = {_norm(u) for u in settings.owner_user_ids}
    return current in allowed


def is_owner_chat(
    settings: Settings,
    chat_id: str | int | None,
    storage: AppStorage | None = None,
) -> bool:
    current = _norm(chat_id)
    if not current:
        return False
    if storage:
        current = storage.resolve_chat_id(current) or current

    allowed = {_norm(c) for c in settings.owner_chat_ids}
    for item in allowed:
        resolved = storage.resolve_chat_id(item) if storage else item
        if _ids_match(current, item) or _ids_match(current, resolved):
            return True
    return False


def is_owner(
    settings: Settings,
    chat_id: str | int | None = None,
    user_id: str | int | None = None,
    storage: AppStorage | None = None,
) -> bool:
    """Владелец: личный user_id (предпочтительно) или owner-чат (временно/тест)."""
    if is_owner_user(settings, user_id):
        return True
    return is_owner_chat(settings, chat_id, storage)


def resolve_session(
    settings: Settings,
    storage: AppStorage,
    chat_id: str | int | None,
    user_id: str | int | None = None,
) -> dict:
    chat_raw = _norm(chat_id)
    chat = storage.resolve_chat_id(chat_raw) if chat_raw else ""
    user = _norm(user_id)

    if is_owner(settings, chat_raw or chat, user, storage):
        return {
            "role": "owner",
            "need_registration": False,
            "chat_id": chat or chat_raw,
            "user_id": user,
            "dropper": None,
            "staff": None,
        }

    staff: StaffMember | None = storage.get_staff_by_user(user) if user else None
    if staff:
        return {
            "role": staff.role,
            "need_registration": False,
            "chat_id": chat or chat_raw,
            "user_id": user,
            "dropper": None,
            "staff": staff.to_dict(),
        }

    dropper: Dropper | None = (
        storage.get_dropper_by_chat(chat or chat_raw) if (chat or chat_raw) else None
    )
    if dropper and dropper.status == "active":
        return {
            "role": "dropper",
            "need_registration": False,
            "chat_id": dropper.chat_id,
            "user_id": user,
            "dropper": dropper.to_dict(),
            "staff": None,
        }

    # Неизвестный групповой чат → регистрация дроппера
    probe = chat or chat_raw
    is_group_chat = probe.startswith("-")
    return {
        "role": "guest",
        "need_registration": bool(is_group_chat),
        "chat_id": probe,
        "user_id": user,
        "dropper": None,
        "staff": None,
    }
