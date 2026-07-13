import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telegram import Bot

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

    return Settings(
        telegram_token=token,
        telegram_chat_id=chat_id,
        email_host=os.getenv("EMAIL_HOST", "imap.gmail.com"),
        email_port=int(os.getenv("EMAIL_PORT", "993")),
        email_user=email_user,
        email_password=email_password,
        poll_interval=config.get("bot", {}).get("poll_interval", 60),
        modules_config=config.get("modules", {}),
    )


class BotContext:
    """Общий контекст для всех модулей."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot = Bot(token=settings.telegram_token)

    async def send_message(
        self,
        text: str,
        button_text: str | None = None,
        button_url: str | None = None,
    ) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        reply_markup = None
        if button_text and button_url:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(button_text, url=button_url)]]
            )

        await self.bot.send_message(
            chat_id=self.settings.telegram_chat_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        logger.info("Сообщение отправлено в Telegram")
