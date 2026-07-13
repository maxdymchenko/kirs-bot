import asyncio
import logging
from typing import TYPE_CHECKING, Any

from modules.base import BaseModule
from modules.email_olx.imap_client import ImapClient

if TYPE_CHECKING:
    from bot.core import BotContext

logger = logging.getLogger(__name__)


class EmailOlxModule(BaseModule):
    name = "email_olx"

    def __init__(self, config: dict[str, Any], bot_context: "BotContext"):
        super().__init__(config, bot_context)
        self._task: asyncio.Task | None = None
        self._processed_uids: set[str] = set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Модуль email_olx запущен")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Модуль email_olx остановлен")

    async def _poll_loop(self) -> None:
        interval = self.ctx.settings.poll_interval
        while True:
            try:
                await self._check_mail()
            except Exception:
                logger.exception("Ошибка при проверке почты")
            await asyncio.sleep(interval)

    async def _check_mail(self) -> None:
        settings = self.ctx.settings
        client = ImapClient(
            host=settings.email_host,
            port=settings.email_port,
            user=settings.email_user,
            password=settings.email_password,
            folder=self.config.get("imap_folder", "INBOX"),
        )

        await asyncio.to_thread(client.connect)
        try:
            emails = await asyncio.to_thread(
                client.fetch_new_emails,
                only_unseen=self.config.get("only_unseen", True),
                sender_filter=self.config.get("sender_filter", ""),
                subject_filter=self.config.get("subject_filter", ""),
                patterns=self.config.get("patterns", {}),
            )

            for parsed in emails:
                if parsed.uid in self._processed_uids:
                    continue

                await self._send_notification(parsed)
                self._processed_uids.add(parsed.uid)

            if self.config.get("mark_as_read", True) and emails:
                uids = [e.uid for e in emails]
                await asyncio.to_thread(client.mark_as_read, uids)
        finally:
            await asyncio.to_thread(client.disconnect)

    async def _send_notification(self, parsed) -> None:
        template = self.config.get(
            "message_template",
            "📩 Новое сообщение на OLX\n\n📧 Аккаунт: {account_email}\n💬 Ссылка: {chat_link}",
        )
        text = template.format(
            account_email=parsed.account_email,
            chat_link=parsed.chat_link,
            subject=parsed.subject,
            from_email=parsed.raw_from,
        )
        button_text = self.config.get("button_text", "Перейти в чат")

        await self.ctx.send_message(
            text=text,
            button_text=button_text,
            button_url=parsed.chat_link,
        )
        logger.info(
            "Уведомление отправлено: аккаунт=%s, ссылка=%s",
            parsed.account_email,
            parsed.chat_link,
        )
