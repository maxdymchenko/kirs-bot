import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from bot.storage import NotificationStorage

logger = logging.getLogger(__name__)


@dataclass
class DropperConfig:
    chat_id: str
    name: str = ""
    require_full_payment: bool = False

    def to_public_dict(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "name": self.name,
            "require_full_payment": self.require_full_payment,
        }


@dataclass
class Settings:
    telegram_token: str
    telegram_chat_id: str
    email_host: str
    email_port: int
    email_user: str
    email_password: str
    poll_interval: int
    modules_config: dict
    pending_commands: list[str] = field(default_factory=lambda: ["neobrabotannye", "pending"])
    owner_chat_ids: list[str] = field(default_factory=list)
    owner_user_ids: list[str] = field(default_factory=list)
    drop_order_chat_ids: list[str] = field(default_factory=list)
    droppers: dict[str, DropperConfig] = field(default_factory=dict)
    webapp_url: str = ""
    app_data_dir: str = ""


def load_settings(config_path: str | Path | None = None) -> Settings:
    load_dotenv()

    config_path = Path(config_path or Path(__file__).resolve().parent.parent / "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    email_user = os.getenv("EMAIL_USER", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан (Render Environment или .env)")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID не задан (Render Environment или .env)")
    if not email_user or not email_password:
        raise ValueError("EMAIL_USER и EMAIL_PASSWORD должны быть заданы (Render Environment или .env)")

    bot_config = config.get("bot", {})
    owner_chats = bot_config.get("owner_chat_ids") or []
    owner_chats = [str(c).strip() for c in owner_chats if str(c).strip()]
    # Временный дефолт, пока владелец не задан явно
    if not owner_chats:
        owner_chats = ["-5396872628"]

    owner_users = bot_config.get("owner_user_ids") or []
    owner_users = [str(u).strip() for u in owner_users if str(u).strip()]
    # Env можно задать через запятую: OWNER_USER_IDS=123,456
    env_owners = os.getenv("OWNER_USER_IDS", "").strip()
    if env_owners:
        for part in env_owners.split(","):
            uid = part.strip()
            if uid and uid not in owner_users:
                owner_users.append(uid)

    drop_chats = bot_config.get("drop_order_chat_ids") or []
    drop_chats = [str(c).strip() for c in drop_chats if str(c).strip()]

    droppers_raw = bot_config.get("droppers") or {}
    droppers: dict[str, DropperConfig] = {}
    if isinstance(droppers_raw, dict):
        for raw_id, raw_cfg in droppers_raw.items():
            chat_key = str(raw_id).strip()
            if not chat_key:
                continue
            cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
            droppers[chat_key] = DropperConfig(
                chat_id=chat_key,
                name=str(cfg.get("name") or "").strip(),
                require_full_payment=bool(cfg.get("require_full_payment", False)),
            )
    for chat_key in drop_chats:
        if chat_key not in droppers:
            droppers[chat_key] = DropperConfig(chat_id=chat_key)

    webapp_url = (
        os.getenv("WEBAPP_URL", "").strip().rstrip("/")
        or os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    )
    app_data = (os.getenv("APP_DATA_DIR") or "").strip()

    return Settings(
        telegram_token=token,
        telegram_chat_id=chat_id,
        email_host=os.getenv("EMAIL_HOST", "imap.gmail.com"),
        email_port=int(os.getenv("EMAIL_PORT", "993")),
        email_user=email_user,
        email_password=email_password,
        poll_interval=bot_config.get("poll_interval", 60),
        modules_config=config.get("modules", {}),
        pending_commands=bot_config.get("pending_commands", ["neobrabotannye", "pending"]),
        owner_chat_ids=owner_chats,
        owner_user_ids=owner_users,
        drop_order_chat_ids=drop_chats,
        droppers=droppers,
        webapp_url=webapp_url,
        app_data_dir=app_data,
    )


class BotContext:
    """Общий контекст для всех модулей."""

    def __init__(
        self,
        settings: Settings,
        storage: NotificationStorage | None = None,
        app_storage=None,
    ):
        from bot.accounts import AppStorage

        self.settings = settings
        self.bot = Bot(token=settings.telegram_token)
        self.storage = storage or NotificationStorage()
        self.app_storage = app_storage or AppStorage()

    async def send_notification(
        self,
        text: str,
        notification_id: int,
        chat_link: str,
        button_text: str,
        processed_button_text: str,
    ) -> int:
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(button_text, url=chat_link)],
            [InlineKeyboardButton(processed_button_text, callback_data=f"done:{notification_id}")],
        ])

        message = await self.bot.send_message(
            chat_id=self.settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        self.storage.set_telegram_message_id(notification_id, message.message_id)
        logger.info("Уведомление #%s отправлено в Telegram", notification_id)
        return message.message_id
