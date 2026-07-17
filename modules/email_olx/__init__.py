import asyncio
import html
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
        processed_uids: list[str] = []
        try:
            emails = await asyncio.to_thread(
                client.fetch_new_emails,
                only_unseen=self.config.get("only_unseen", True),
                sender_filter=self.config.get("sender_filter", ""),
                patterns=self.config.get("patterns", {}),
                allowed_subjects=self.config.get("allowed_subjects", []),
                required_sender=self.config.get("sender_filter", ""),
                allowed_link_paths=self.config.get("allowed_link_paths", []),
            )

            for parsed in emails:
                if self.ctx.storage.get_by_email_uid(parsed.uid):
                    processed_uids.append(parsed.uid)
                    continue

                sent = await self._send_notification(parsed)
                if sent:
                    processed_uids.append(parsed.uid)

            if self.config.get("mark_as_read", True) and processed_uids:
                await asyncio.to_thread(client.mark_as_read, processed_uids)
        finally:
            await asyncio.to_thread(client.disconnect)

    def _resolve_title(self, subject: str) -> str:
        subject_lower = subject.lower()
        for rule in self.config.get("title_rules", []):
            needles = rule.get("subject_contains") or []
            if isinstance(needles, str):
                needles = [needles]
            for needle in needles:
                if needle and needle.lower() in subject_lower:
                    return str(rule.get("title") or self.config.get("default_title", "Повідомлення OLX"))
        return str(self.config.get("default_title", "Повідомлення OLX"))

    async def _send_notification(self, parsed) -> bool:
        title = self._resolve_title(parsed.subject)
        template = self.config.get(
            "message_template",
            '<b>📩 {title} <a href="{chat_link}">#{anchor_id}</a></b>\n\n'
            "📧 Аккаунт: {account_email}",
        )
        button_text = self.config.get("button_text", "Перейти в чат")
        processed_button_text = self.config.get("processed_button_text", "✅ Обработано")

        notification = self.ctx.storage.create(
            email_uid=parsed.uid,
            account_email=parsed.account_email,
            chat_link=parsed.chat_link,
            subject=parsed.subject,
            message_text="",
            telegram_chat_id=self.ctx.settings.telegram_chat_id,
        )

        text = template.format(
            title=html.escape(title),
            anchor_id=notification.anchor_id,
            account_email=html.escape(parsed.account_email),
            chat_link=html.escape(parsed.chat_link, quote=True),
            subject=html.escape(parsed.subject),
            from_email=html.escape(parsed.raw_from),
        )
        self.ctx.storage.update_message_text(notification.id, text)

        try:
            await self.ctx.send_notification(
                text=text,
                notification_id=notification.id,
                chat_link=parsed.chat_link,
                button_text=button_text,
                processed_button_text=processed_button_text,
            )
        except Exception:
            logger.exception("Не удалось отправить уведомление #%s", notification.anchor_id)
            self.ctx.storage.delete(notification.id)
            return False

        logger.info(
            "Уведомление #%s отправлено: title=%s, аккаунт=%s",
            notification.anchor_id,
            title,
            parsed.account_email,
        )
        return True
