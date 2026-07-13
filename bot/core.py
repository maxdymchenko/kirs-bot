import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.storage import NotificationStorage

logger = logging.getLogger(__name__)


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
    )


class BotContext:
    """Общий контекст для всех модулей."""

    def __init__(self, settings: Settings, storage: NotificationStorage | None = None):
        self.settings = settings
        self.bot = Bot(token=settings.telegram_token)
        self.storage = storage or NotificationStorage()

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
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        self.storage.set_telegram_message_id(notification_id, message.message_id)
        logger.info("Уведомление #%s отправлено в Telegram", notification_id)
        return message.message_id
