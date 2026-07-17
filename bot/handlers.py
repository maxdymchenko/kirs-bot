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
    application.add_handler(
        CallbackQueryHandler(mark_done_callback, pattern=f"^{DONE_CALLBACK_PREFIX}")
    )


def _is_drop_order_chat(ctx: BotContext, chat_id: int | None) -> bool:
    if chat_id is None:
        return False
    allowed = {str(c) for c in ctx.settings.drop_order_chat_ids}
    return str(chat_id) in allowed


async def order_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню оформления заказа — только в разрешённых чатах."""
    if not update.effective_chat or not update.message:
        return

    ctx: BotContext = context.bot_data["ctx"]
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    if not _is_drop_order_chat(ctx, chat_id):
        if update.message.text and update.message.text.startswith("/menu"):
            await update.message.reply_text("Меню замовлень у цьому чаті недоступне.")
        return

    webapp_url = ctx.settings.webapp_url
    if not webapp_url:
        await update.message.reply_text(
            "Mini App ще не налаштовано: задайте WEBAPP_URL (або RENDER_EXTERNAL_URL на Render)."
        )
        return

    from telegram import MenuButtonWebApp

    await context.bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(
            text="Замовлення",
            web_app=WebAppInfo(url=webapp_url),
        ),
    )

    # В личке можно открыть WebApp прямо кнопкой в сообщении.
    # В группе — только через кнопку меню возле поля ввода.
    if chat_type == "private":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Оформити замовлення",
                        web_app=WebAppInfo(url=webapp_url),
                    )
                ]
            ]
        )
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    await update.message.reply_text(
        "Меню:\n\n"
        "1) Натисніть кнопку <b>Замовлення</b> біля поля вводу повідомлення "
        "(ліворуч від скріпки / меню чату).\n"
        "2) Оберіть <b>Оформити замовлення</b> у відкритому вікні "
        "(пошук по коду → кошик).",
        parse_mode=ParseMode.HTML,
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
