import html
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.core import BotContext
from bot.roles import resolve_session
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
        MessageHandler(
            filters.StatusUpdate.MIGRATE,
            chat_migrated_handler,
        )
    )
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


def _webapp_url_with_context(
    base_url: str,
    chat_id: int | str | None = None,
    user_id: int | str | None = None,
    view: str | None = None,
) -> str:
    """В групах Telegram відкриває звичайний браузер — передаємо контекст у query."""
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if chat_id is not None and str(chat_id).strip():
        query["chat_id"] = str(chat_id).strip()
    if user_id is not None and str(user_id).strip():
        query["user_id"] = str(user_id).strip()
    if view:
        query["view"] = str(view).strip()
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment)
    )


def _webapp_button(
    text: str,
    webapp_url: str,
    chat_type: str,
    chat_id: int | str | None = None,
    user_id: int | str | None = None,
    view: str | None = None,
) -> InlineKeyboardButton:
    # У private чатах Telegram відкриває справжній Mini App (є initData).
    url = _webapp_url_with_context(webapp_url, chat_id=chat_id, user_id=user_id, view=view)
    if chat_type == "private":
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    # У групах web_app-кнопки заборонені → звичайне посилання з chat_id/user_id.
    return InlineKeyboardButton(text=text, url=url)


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    chat = update.effective_chat
    user = update.effective_user
    user_line = ""
    if user:
        user_line = (
            f"\nваш user_id: `{user.id}` "
            f"(це постійний id — його додають у owner_user_ids)"
        )
    await update.message.reply_text(
        f"chat_id: `{chat.id}`\n"
        f"type: {chat.type}\n"
        f"title: {chat.title or '-'}"
        f"{user_line}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def chat_migrated_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Автоперепис chat_id при апгрейде group → supergroup."""
    message = update.effective_message
    if not message:
        return

    ctx: BotContext = context.bot_data["ctx"]
    old_id: int | None = None
    new_id: int | None = None

    if message.migrate_to_chat_id:
        old_id = message.chat_id
        new_id = message.migrate_to_chat_id
    elif message.migrate_from_chat_id:
        old_id = message.migrate_from_chat_id
        new_id = message.chat_id

    if old_id is None or new_id is None:
        return

    result = ctx.app_storage.migrate_chat_id(old_id, new_id)
    logger.info("Telegram migrate event: %s", result)

    # Обновить TELEGRAM_CHAT_ID в рантайме, если это OLX-чат
    if str(ctx.settings.telegram_chat_id).strip() == str(old_id):
        ctx.settings.telegram_chat_id = str(new_id)
        logger.info("Обновлён settings.telegram_chat_id → %s", new_id)

    # Обновить owner_chat_ids в рантайме
    updated_owners: list[str] = []
    for chat in ctx.settings.owner_chat_ids:
        if str(chat).strip() == str(old_id):
            updated_owners.append(str(new_id))
        else:
            updated_owners.append(chat)
    ctx.settings.owner_chat_ids = updated_owners

    # Обновить yaml-droppers ключ в рантайме
    if str(old_id) in ctx.settings.droppers:
        cfg = ctx.settings.droppers.pop(str(old_id))
        cfg.chat_id = str(new_id)
        ctx.settings.droppers[str(new_id)] = cfg

    notify_text = (
        "♻️ Чат оновлено (group → supergroup).\n"
        f"Старий chat_id: `{old_id}`\n"
        f"Новий chat_id: `{new_id}`\n"
        "Базу оновлено автоматично, нічого вручну міняти не потрібно."
    )
    try:
        await context.bot.send_message(
            chat_id=new_id,
            text=notify_text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        logger.exception("Не удалось уведомить чат о миграции %s → %s", old_id, new_id)

    for owner_chat in ctx.settings.owner_chat_ids:
        try:
            await context.bot.send_message(
                chat_id=owner_chat,
                text=notify_text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.exception("Не удалось уведомить owner %s о миграции", owner_chat)
    for owner_user in ctx.settings.owner_user_ids:
        try:
            await context.bot.send_message(
                chat_id=owner_user,
                text=notify_text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.exception("Не удалось уведомить owner user %s о миграции", owner_user)


async def order_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    ctx: BotContext = context.bot_data["ctx"]
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id if update.effective_user else None

    session = resolve_session(ctx.settings, ctx.app_storage, chat_id, user_id)
    role = session.get("role")
    need_registration = bool(session.get("need_registration"))

    logger.info(
        "Команда меню: chat_id=%s type=%s role=%s need_reg=%s webapp=%s",
        chat_id,
        chat_type,
        role,
        need_registration,
        ctx.settings.webapp_url or "-",
    )

    webapp_url = ctx.settings.webapp_url
    if not webapp_url:
        await update.message.reply_text(
            "Mini App ще не налаштовано.\n"
            "У Render Environment задайте:\n"
            "`WEBAPP_URL=https://kirs-bot-web.onrender.com`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if role == "owner":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    _webapp_button(
                        "Кабінет власника",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                    )
                ],
                [
                    _webapp_button(
                        "Баланси / реферали",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                        view="balances",
                    )
                ],
            ]
        )
        await update.message.reply_text(
            "Меню власника:\n\nКерування дропперами та співробітниками.",
            reply_markup=keyboard,
        )
        return

    if role in {"admin", "manager", "warehouse"}:
        await update.message.reply_text(
            f"Роль: {role}.\nКабінет співробітника з’явиться наступним етапом."
        )
        return

    if role == "dropper":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    _webapp_button(
                        "Зробити замовлення",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                    )
                ],
                [
                    _webapp_button(
                        "Мій баланс",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                        view="balance",
                    )
                ],
                [
                    _webapp_button(
                        "Історія замовлень",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                        view="history",
                    )
                ],
            ]
        )
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    if role == "dropper_blocked":
        await update.message.reply_text(
            "⛔ Вас заблоковано для повного погашення боргу.\n"
            "Передача замовлень недоступна. Звʼяжіться з власником."
        )
        return

    if need_registration:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    _webapp_button(
                        "Зареєструвати дроппера",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                    )
                ]
            ]
        )
        await update.message.reply_text(
            "Цю групу ще не зареєстровано як дроппера.\n"
            "Натисніть кнопку нижче, щоб пройти реєстрацію один раз.",
            reply_markup=keyboard,
        )
        return

    await update.message.reply_text(
        "Меню недоступне в цьому чаті.\n"
        f"chat_id: `{chat_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: BotContext = context.bot_data["ctx"]
    storage: NotificationStorage = ctx.storage
    pending = storage.list_unprocessed()

    if not pending:
        await update.message.reply_text(
            "✅ У базі немає необроблених чатів."
        )
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
        # Старе повідомлення в Telegram після wipe БД / зміни APP_DATA_DIR
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            logger.exception("Не вдалося прибрати кнопки у застарілому повідомленні")
        await query.answer("Запис застарів (немає в БД)", show_alert=True)
        return

    user = query.from_user
    user_label = (
        f"@{user.username}" if user and user.username else (user.full_name if user else "менеджер")
    )

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
