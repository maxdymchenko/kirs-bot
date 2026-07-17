import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.core import BotContext
from bot.storage import NotificationStorage

logger = logging.getLogger(__name__)

DONE_CALLBACK_PREFIX = "done:"


def register_handlers(application: Application, ctx: BotContext) -> None:
    pending_commands = ctx.settings.pending_commands
    for command in pending_commands:
        application.add_handler(CommandHandler(command, pending_command))

    application.add_handler(CommandHandler(["menu", "start"], order_menu_command))
    application.add_handler(CommandHandler("chatid", chat_id_command))
    application.add_handler(
        CallbackQueryHandler(mark_done_callback, pattern=f"^{DONE_CALLBACK_PREFIX}")
    )
    application.add_error_handler(on_error)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка обработчика Telegram: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Сталася помилка обробки команди. Спробуйте /menu ще раз."
            )
        except Exception:
            pass


def _is_drop_order_chat(ctx: BotContext, chat_id: int | None) -> bool:
    if chat_id is None:
        return False
    allowed = {str(c) for c in ctx.settings.drop_order_chat_ids}
    current = str(chat_id)
    if current in allowed:
        return True
    # После апгрейда группы в супергруппу id может стать -100...
    for item in allowed:
        if current.endswith(item.lstrip("-")) or item.endswith(current.lstrip("-")):
            return True
    return False


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    chat = update.effective_chat
    await update.message.reply_text(
        f"chat_id: `{chat.id}`\n"
        f"type: {chat.type}\n"
        f"title: {chat.title or '-'}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def order_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню оформления заказа — только в разрешённых чатах."""
    if not update.effective_chat or not update.message:
        return

    ctx: BotContext = context.bot_data["ctx"]
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    logger.info(
        "Команда меню: chat_id=%s type=%s text=%s allowed=%s webapp=%s",
        chat_id,
        chat_type,
        update.message.text,
        _is_drop_order_chat(ctx, chat_id),
        ctx.settings.webapp_url or "-",
    )

    if not _is_drop_order_chat(ctx, chat_id):
        await update.message.reply_text(
            "Меню замовлень у цьому чаті недоступне.\n"
            f"chat_id цього чату: `{chat_id}`\n"
            "Надішліть цей id, якщо меню має працювати тут.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    webapp_url = ctx.settings.webapp_url
    if not webapp_url:
        await update.message.reply_text(
            "Mini App ще не налаштовано.\n"
            "У Render Environment задайте:\n"
            "`WEBAPP_URL=https://kirs-bot-web.onrender.com`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    if chat_type == "private":
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Оформити замовлення",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ]
        )
    else:
        # В группе inline web_app недоступен — открываем HTTPS-форму кнопкой-ссылкой.
        keyboard_rows.append(
            [InlineKeyboardButton(text="Відкрити форму замовлення", url=webapp_url)]
        )

    await update.message.reply_text(
        "Меню:\n\nНатисніть кнопку нижче, щоб відкрити форму "
        "(пошук по коду → кошик).",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )

    try:
        from telegram import MenuButtonWebApp

        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="Замовлення",
                web_app=WebAppInfo(url=webapp_url),
            ),
        )
    except Exception:
        logger.exception("Не удалось установить MenuButtonWebApp для chat_id=%s", chat_id)
        await update.message.reply_text(
            "Кнопку меню чату не вдалося увімкнути автоматично. "
            "Форму можна відкрити кнопкою вище."
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


async def mark_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    ctx: BotContext = context.bot_data["ctx"]
    storage: NotificationStorage = ctx.storage

    try:
        notification_id = int(query.data.removeprefix(DONE_CALLBACK_PREFIX))
    except ValueError:
        await query.answer("Некорректная кнопка")
        return

    notification = storage.get(notification_id)
    if not notification:
        await query.answer("Уведомление не найдено")
        return

    user = query.from_user
    user_label = f"@{user.username}" if user and user.username else (user.full_name if user else "менеджер")

    if notification.processed:
        await query.answer("Уже обработано")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    storage.mark_processed(notification_id, user_label)
    message_text = notification.message_text
    if "<b>" not in message_text or "<a href=" not in message_text:
        message_text = html.escape(message_text)
    updated_text = (
        f"{message_text}\n\n"
        f"✅ Обработано #{notification.anchor_id} ({html.escape(user_label)})"
    )
    await query.edit_message_text(
        text=updated_text,
        parse_mode=ParseMode.HTML,
        reply_markup=None,
        disable_web_page_preview=True,
    )
    await query.answer("Отмечено как обработано")

    logger.info(
        "Чат #%s отмечен обработанным пользователем %s",
        notification.anchor_id,
        user_label,
    )
