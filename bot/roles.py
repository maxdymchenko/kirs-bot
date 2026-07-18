"""Определение роли по chat_id / user_id."""

from __future__ import annotations

from bot.accounts import AppStorage, Dropper, StaffMember
from bot.core import Settings


def _norm(value: str | int | None) -> str:
    return str(value or "").strip()


def is_owner_chat(settings: Settings, chat_id: str | int | None) -> bool:
    current = _norm(chat_id)
    if not current:
        return False
    allowed = {_norm(c) for c in settings.owner_chat_ids}
    if current in allowed:
        return True
    for item in allowed:
        if current.endswith(item.lstrip("-")) or item.endswith(current.lstrip("-")):
            return True
    return False


def resolve_session(
    settings: Settings,
    storage: AppStorage,
    chat_id: str | int | None,
    user_id: str | int | None = None,
) -> dict:
    chat = _norm(chat_id)
    user = _norm(user_id)

    if is_owner_chat(settings, chat):
        return {
            "role": "owner",
            "need_registration": False,
            "chat_id": chat,
            "user_id": user,
            "dropper": None,
            "staff": None,
        }

    staff: StaffMember | None = storage.get_staff_by_user(user) if user else None
    if staff:
        return {
            "role": staff.role,
            "need_registration": False,
            "chat_id": chat,
            "user_id": user,
            "dropper": None,
            "staff": staff.to_dict(),
        }

    dropper: Dropper | None = storage.get_dropper_by_chat(chat) if chat else None
    if dropper and dropper.status == "active":
        return {
            "role": "dropper",
            "need_registration": False,
            "chat_id": chat,
            "user_id": user,
            "dropper": dropper.to_dict(),
            "staff": None,
        }

    # Неизвестный групповой чат → регистрация дроппера
    is_group_chat = chat.startswith("-")
    return {
        "role": "guest",
        "need_registration": bool(is_group_chat),
        "chat_id": chat,
        "user_id": user,
        "dropper": None,
        "staff": None,
    }
