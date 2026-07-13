import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.core import BotContext
from bot.storage import NotificationStorage

logger = logging.getLogger(__name__)

OPEN_CALLBACK_PREFIX = "open:"


def register_handlers(application: Application, ctx: BotContext) -> None:
    pending_commands = ctx.settings.pending_commands
    for command in pending_commands:
        application.add_handler(CommandHandler(command, pending_command))

    application.add_handler(
        CallbackQueryHandler(open_chat_callback, pattern=f"^{OPEN_CALLBACK_PREFIX}")
    )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: BotContext = context.bot_data["ctx"]
    storage: NotificationStorage = ctx.storage
    pending = storage.list_unprocessed()

    if not pending:
        await update.message.reply_text("✅ Все чаты обработаны.")
        return

    lines = [f"⏳ Необработанные чаты ({len(pending)}):", ""]
    for item in pending:
        lines.append(f"#{item.anchor_id} — {item.account_email}")
        lines.append(f"   {item.chat_link}")
        lines.append("")

    await update.message.reply_text("\n".join(lines).strip(), disable_web_page_preview=True)


async def open_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    ctx: BotContext = context.bot_data["ctx"]
    storage: NotificationStorage = ctx.storage

    try:
        notification_id = int(query.data.removeprefix(OPEN_CALLBACK_PREFIX))
    except ValueError:
        await query.answer("Некорректная кнопка")
        return

    notification = storage.get(notification_id)
    if not notification:
        await query.answer("Уведомление не найдено")
        return

    user = query.from_user
    user_label = f"@{user.username}" if user and user.username else (user.full_name if user else "менеджер")

    if not notification.processed:
        storage.mark_processed(notification_id, user_label)
        updated_text = (
            f"{notification.message_text}\n\n"
            f"✅ Обработано #{notification.anchor_id} ({user_label})"
        )
        await query.edit_message_text(
            text=updated_text,
            reply_markup=None,
            disable_web_page_preview=True,
        )
    else:
        await query.edit_message_reply_markup(reply_markup=None)

    try:
        await query.answer(url=notification.chat_link)
    except Exception:
        await query.answer("Ссылка открыта. Если браузер не открылся — используйте ссылку в сообщении.")

    logger.info(
        "Чат #%s отмечен обработанным пользователем %s",
        notification.anchor_id,
        user_label,
    )
