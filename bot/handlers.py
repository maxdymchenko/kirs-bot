import html
import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
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

# Reply-клавіатура (кнопки над полем «Сообщение…»)
BTN_CABINET = "Кабінет"
BTN_WAREHOUSE = "Кабінет комірника"
BTN_ORDER = "Замовлення"
BTN_BALANCE = "Баланс"
BTN_HISTORY = "Історія"
BTN_MENU = "Меню"
BTN_CHAT_ID = "Chat ID"
BTN_STOCK = "Наявність"
BTN_STOCK_CANCEL = "Скасувати наявність"
BTN_TO_ORDER = "Замовити"
BTN_TO_ORDER_CANCEL = "Скасувати список"

_REPLY_BUTTON_TEXTS = frozenset(
    {
        BTN_CABINET,
        BTN_WAREHOUSE,
        BTN_ORDER,
        BTN_BALANCE,
        BTN_HISTORY,
        BTN_MENU,
        BTN_CHAT_ID,
        BTN_STOCK,
        BTN_STOCK_CANCEL,
        BTN_TO_ORDER,
        BTN_TO_ORDER_CANCEL,
    }
)

# Рядки наявності: 010=розовое золото=-2  |  010 = 4  |  010 | Золотой = 5
_AWAITING_STOCK_KEY = "awaiting_stock_adjust"
_AWAITING_TO_ORDER_KEY = "awaiting_to_order"


def register_handlers(application: Application, ctx: BotContext) -> None:
    pending_commands = ctx.settings.pending_commands
    for command in pending_commands:
        application.add_handler(CommandHandler(command, pending_command))

    application.add_handler(CommandHandler(["menu", "start"], order_menu_command))
    application.add_handler(CommandHandler("chatid", chat_id_command))
    application.add_handler(CommandHandler("stock", stock_adjust_start))
    application.add_handler(CommandHandler(["toorder", "orderlist"], to_order_start))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(_reply_buttons_regex()),
            reply_keyboard_handler,
        )
    )
    # Режим наявності / список «Замовити» / «код - заказан»
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_modes_handler,
        )
    )
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


def _reply_buttons_regex() -> str:
    """Точний збіг тексту однієї з кнопок reply-клавіатури."""
    escaped = sorted(_REPLY_BUTTON_TEXTS, key=len, reverse=True)
    parts = [re.escape(t) for t in escaped]
    return r"^(?:%s)$" % "|".join(parts)


async def setup_bot_commands(application: Application, ctx: BotContext) -> None:
    """Slash-меню ≡ біля поля вводу."""
    commands = [
        BotCommand("start", "Меню / кабінет"),
        BotCommand("menu", "Меню / кабінет"),
        BotCommand("chatid", "Показати chat_id"),
        BotCommand("stock", "Коригування наявності"),
        BotCommand("toorder", "Список «Замовити»"),
    ]
    for name in ctx.settings.pending_commands or []:
        key = str(name or "").strip().lstrip("/")
        if not key or key in {"start", "menu", "chatid", "stock", "toorder", "orderlist"}:
            continue
        commands.append(BotCommand(key, "Необроблені чати OLX"))
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Telegram bot commands set: %s", [c.command for c in commands])
    except Exception:
        logger.exception("Не вдалося set_my_commands")


def build_reply_keyboard(
    role: str | None,
    *,
    need_registration: bool = False,
    stock_mode: bool = False,
    to_order_mode: bool = False,
) -> ReplyKeyboardMarkup:
    """Постійна клавіатура над полем вводу — залежить від ролі чату."""
    if stock_mode:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(BTN_STOCK_CANCEL)]],
            resize_keyboard=True,
            is_persistent=True,
        )
    if to_order_mode:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(BTN_TO_ORDER_CANCEL)]],
            resize_keyboard=True,
            is_persistent=True,
        )
    if role == "owner":
        rows = [
            [KeyboardButton(BTN_CABINET), KeyboardButton(BTN_STOCK)],
            [KeyboardButton(BTN_TO_ORDER), KeyboardButton(BTN_CHAT_ID)],
        ]
    elif role == "warehouse":
        rows = [
            [KeyboardButton(BTN_WAREHOUSE), KeyboardButton(BTN_STOCK)],
            [KeyboardButton(BTN_CHAT_ID)],
        ]
    elif role == "dropper":
        rows = [
            [KeyboardButton(BTN_ORDER), KeyboardButton(BTN_BALANCE)],
            [KeyboardButton(BTN_HISTORY), KeyboardButton(BTN_CHAT_ID)],
        ]
    elif role in {"admin", "manager"}:
        rows = [[KeyboardButton(BTN_MENU), KeyboardButton(BTN_CHAT_ID)]]
    elif need_registration or role in {None, "", "unknown", "guest"}:
        rows = [[KeyboardButton(BTN_MENU), KeyboardButton(BTN_CHAT_ID)]]
    else:
        rows = [[KeyboardButton(BTN_MENU), KeyboardButton(BTN_CHAT_ID)]]
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def _can_adjust_stock(role: str | None) -> bool:
    return role in {"owner", "warehouse"}


def _can_manage_to_order(role: str | None) -> bool:
    return role == "owner"


def parse_stock_adjust_text(text: str) -> tuple[list[dict], list[str]]:
    """
    Розбір рядків наявності. Колір опційний. Приклади:
      010=розовое золото=-2
      010 = золото = 5
      010 = Розовое золото=-3
      010=Розовое золото =4
      010=-5
      010 =4
      010 = 3
      010 | Розовое золото = 5
    """
    adjustments: list[dict] = []
    errors: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # | або ; між кодом і кольором → той самий роздільник, що =
        normalized = re.sub(r"\s*[|;]\s*", "=", line)
        parts = [p.strip() for p in normalized.split("=") if p.strip()]
        if len(parts) < 2:
            errors.append(f"не розпізнано: {line}")
            continue
        delta_raw = parts[-1].replace(" ", "")
        try:
            delta = int(delta_raw)
        except ValueError:
            errors.append(f"некоректна кількість: {line}")
            continue
        code = parts[0].strip().lstrip("'")
        if not code:
            errors.append(f"порожній код: {line}")
            continue
        color = " ".join(parts[1:-1]).strip() if len(parts) > 2 else ""
        adjustments.append({"code": code, "color": color, "delta": delta})
    return adjustments, errors


def _stock_chat_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.chat_data


def _set_awaiting_stock(context: ContextTypes.DEFAULT_TYPE, value: bool) -> None:
    if value:
        _stock_chat_data(context)[_AWAITING_STOCK_KEY] = True
        _stock_chat_data(context).pop(_AWAITING_TO_ORDER_KEY, None)
    else:
        _stock_chat_data(context).pop(_AWAITING_STOCK_KEY, None)


def _is_awaiting_stock(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(_stock_chat_data(context).get(_AWAITING_STOCK_KEY))


def _set_awaiting_to_order(context: ContextTypes.DEFAULT_TYPE, value: bool) -> None:
    if value:
        _stock_chat_data(context)[_AWAITING_TO_ORDER_KEY] = True
        _stock_chat_data(context).pop(_AWAITING_STOCK_KEY, None)
    else:
        _stock_chat_data(context).pop(_AWAITING_TO_ORDER_KEY, None)


def _is_awaiting_to_order(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(_stock_chat_data(context).get(_AWAITING_TO_ORDER_KEY))


async def stock_adjust_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Увімкнути режим введення списку наявності."""
    if not update.effective_chat or not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    if not _can_adjust_stock(role):
        await update.message.reply_text(
            "Коригування наявності доступне власнику та комірнику.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return
    if ctx.catalog is None:
        await update.message.reply_text(
            "Каталог не підключено до бота. Спробуйте пізніше.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return

    _set_awaiting_stock(context, True)
    await update.message.reply_text(
        "Надішліть список змін наявності (по одному в рядку).\n"
        "Колір — за бажанням.\n\n"
        "З кольором:\n"
        "`010=розовое золото=-2`\n"
        "`010 = золото = 5`\n"
        "`010 = Розовое золото=-3`\n"
        "`010=Розовое золото =4`\n\n"
        "Без кольору (якщо варіант один, або уточнить бот):\n"
        "`010=-5`\n"
        "`010 =4`\n"
        "`010 = 3`\n\n"
        f"Або натисніть «{BTN_STOCK_CANCEL}».",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_reply_keyboard(role, need_registration=need_reg, stock_mode=True),
    )


async def stock_adjust_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    _set_awaiting_stock(context, False)
    await update.message.reply_text(
        "Режим наявності скасовано.",
        reply_markup=build_reply_keyboard(role, need_registration=need_reg),
    )


async def to_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Увімкнути режим списку закупівель «Замовити»."""
    if not update.effective_chat or not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    if not _can_manage_to_order(role):
        await update.message.reply_text(
            "Список «Замовити» доступний лише власнику.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return
    if ctx.app_storage is None:
        await update.message.reply_text(
            "Сховище не підключено.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return

    from bot.to_order import format_pending_list

    _set_awaiting_to_order(context, True)
    items = ctx.app_storage.list_to_order_pending()
    await update.message.reply_text(
        format_pending_list(items)
        + "\n\nНадішліть код (або кілька рядків кодів) — додаю в список.\n"
        "Після замовлення: `1231 - заказан`\n\n"
        f"«{BTN_TO_ORDER_CANCEL}» — вийти з режиму (список лишається).",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_reply_keyboard(
            role, need_registration=need_reg, to_order_mode=True
        ),
    )


async def to_order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    _set_awaiting_to_order(context, False)
    await update.message.reply_text(
        "Режим списку «Замовити» вимкнено. Щоденне нагадування о 9:00 лишається.",
        reply_markup=build_reply_keyboard(role, need_registration=need_reg),
    )


async def text_modes_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Маршрутизатор текстових режимів: наявність / замовити / «код - заказан»."""
    if not update.message or not update.message.text:
        return

    if _is_awaiting_stock(context):
        await stock_adjust_text_handler(update, context)
        return

    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    text = update.message.text.strip()

    from bot.to_order import parse_ordered_code, parse_to_order_codes, format_pending_list

    ordered_code = parse_ordered_code(text)
    if ordered_code and _can_manage_to_order(role) and ctx.app_storage is not None:
        user_id = str(update.effective_user.id) if update.effective_user else ""
        saved = ctx.app_storage.mark_to_order_ordered(
            ordered_code, ordered_by_user_id=user_id
        )
        kb = build_reply_keyboard(
            role,
            need_registration=need_reg,
            to_order_mode=_is_awaiting_to_order(context),
        )
        if saved:
            left = ctx.app_storage.list_to_order_pending()
            await update.message.reply_text(
                f"✅ {saved['product_code']} — знято зі списку.\n"
                f"Залишилось: {len(left)}",
                reply_markup=kb,
            )
        else:
            await update.message.reply_text(
                f"Коду `{ordered_code}` немає в списку «Замовити».",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb,
            )
        return

    if not _is_awaiting_to_order(context):
        return

    if not _can_manage_to_order(role) or ctx.app_storage is None:
        _set_awaiting_to_order(context, False)
        await update.message.reply_text(
            "Немає доступу до списку «Замовити».",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return

    codes = parse_to_order_codes(text)
    if not codes:
        await update.message.reply_text(
            "Надішліть код товару (по одному в рядку) або `код - заказан`.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_reply_keyboard(
                role, need_registration=need_reg, to_order_mode=True
            ),
        )
        return

    user_id = str(update.effective_user.id) if update.effective_user else ""
    added: list[str] = []
    exists: list[str] = []
    for code in codes:
        try:
            _entry, created = ctx.app_storage.add_to_order(
                code, created_by_user_id=user_id
            )
        except ValueError:
            continue
        if created:
            added.append(code)
        else:
            exists.append(code)

    lines: list[str] = []
    if added:
        lines.append(f"✅ Додано ({len(added)}): " + ", ".join(added))
    if exists:
        lines.append(f"ℹ️ Вже в списку: " + ", ".join(exists))
    if not lines:
        lines.append("Нічого не додано.")
    items = ctx.app_storage.list_to_order_pending()
    lines.append("")
    lines.append(format_pending_list(items))
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_reply_keyboard(
            role, need_registration=need_reg, to_order_mode=True
        ),
    )


async def stock_adjust_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Приймає список кодів лише в режимі awaiting_stock."""
    if not update.message or not update.message.text:
        return
    if not _is_awaiting_stock(context):
        return

    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    if not _can_adjust_stock(role):
        _set_awaiting_stock(context, False)
        await update.message.reply_text(
            "Немає доступу до коригування наявності.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return

    text = update.message.text.strip()
    adjustments, parse_errors = parse_stock_adjust_text(text)
    if not adjustments and parse_errors:
        await update.message.reply_text(
            "Не вдалося розпізнати список.\n"
            "Приклади: `010=розовое золото=-2` або `010 = 4`\n\n"
            + "\n".join(f"• {e}" for e in parse_errors[:10]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_reply_keyboard(
                role, need_registration=need_reg, stock_mode=True
            ),
        )
        return
    if not adjustments:
        await update.message.reply_text(
            "Порожнє повідомлення. Надішліть, наприклад: `010 = Розовое золото = 5`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_reply_keyboard(
                role, need_registration=need_reg, stock_mode=True
            ),
        )
        return

    if ctx.catalog is None:
        _set_awaiting_stock(context, False)
        await update.message.reply_text(
            "Каталог не підключено.",
            reply_markup=build_reply_keyboard(role, need_registration=need_reg),
        )
        return

    await update.message.reply_text("Записую в таблицю наявності…")
    try:
        import asyncio

        result = await asyncio.to_thread(ctx.catalog.apply_stock_adjustments, adjustments)
    except Exception:
        logger.exception("stock adjust failed")
        await update.message.reply_text(
            "Помилка запису в Google Sheets. Спробуйте ще раз.",
            reply_markup=build_reply_keyboard(
                role, need_registration=need_reg, stock_mode=True
            ),
        )
        return

    _set_awaiting_stock(context, False)
    lines: list[str] = []
    applied = result.get("applied") or []
    errors = list(result.get("errors") or [])
    for e in parse_errors:
        errors.append({"code": "?", "error": e})

    if applied:
        lines.append(f"✅ Оновлено ({len(applied)}):")
        for row in applied:
            sign = "+" if int(row["delta"]) > 0 else ""
            color = f" · {row['color']}" if row.get("color") else ""
            lines.append(
                f"• {row['code']}{color}: {row['before']} → {row['after']} "
                f"({sign}{row['delta']})"
            )
    if errors:
        lines.append("")
        lines.append(f"⚠️ Помилки ({len(errors)}):")
        for err in errors[:20]:
            lines.append(f"• {err.get('code', '?')}: {err.get('error', '')}")

    if not lines:
        lines.append("Нічого не змінено.")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=build_reply_keyboard(role, need_registration=need_reg),
    )


def _session_role(ctx: BotContext, update: Update) -> tuple[str | None, bool]:
    chat = update.effective_chat
    user = update.effective_user
    if not chat:
        return None, False
    session = resolve_session(
        ctx.settings,
        ctx.app_storage,
        chat.id,
        user.id if user else None,
    )
    return session.get("role"), bool(session.get("need_registration"))


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


async def _reply_menu_and_inline(
    message,
    *,
    text: str,
    reply_kb: ReplyKeyboardMarkup,
    inline: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    """Спочатку reply-клавіатура, потім (за потреби) inline-кнопки Mini App."""
    kwargs: dict = {"reply_markup": reply_kb}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    await message.reply_text(text, **kwargs)
    if inline is not None:
        await message.reply_text("Відкрити:", reply_markup=inline)


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    role, need_reg = _session_role(ctx, update)
    reply_kb = build_reply_keyboard(role, need_registration=need_reg)
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
        reply_markup=reply_kb,
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

    # Група звітів наявності
    if str(ctx.settings.stock_digest_chat_id).strip() == str(old_id):
        ctx.settings.stock_digest_chat_id = str(new_id)
        logger.info("Обновлён settings.stock_digest_chat_id → %s", new_id)

    # Група дайджесту пакування
    if str(ctx.settings.packing_digest_chat_id).strip() == str(old_id):
        ctx.settings.packing_digest_chat_id = str(new_id)
        logger.info("Обновлён settings.packing_digest_chat_id → %s", new_id)

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


async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Натискання кнопки reply-клавіатури → та сама логіка, що й у slash-команд."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if text == BTN_STOCK_CANCEL:
        await stock_adjust_cancel(update, context)
        return
    if text == BTN_TO_ORDER_CANCEL:
        await to_order_cancel(update, context)
        return
    if text == BTN_STOCK:
        await stock_adjust_start(update, context)
        return
    if text == BTN_TO_ORDER:
        await to_order_start(update, context)
        return
    # Інші кнопки меню виходять з режимів введення
    if _is_awaiting_stock(context):
        _set_awaiting_stock(context, False)
    if _is_awaiting_to_order(context):
        _set_awaiting_to_order(context, False)
    if text == BTN_CHAT_ID:
        await chat_id_command(update, context)
        return
    if text in {BTN_CABINET, BTN_WAREHOUSE, BTN_ORDER, BTN_MENU}:
        await order_menu_command(update, context)
        return
    if text == BTN_BALANCE:
        await dropper_quick_view(update, context, view="balance", title="Мій баланс")
        return
    if text == BTN_HISTORY:
        await dropper_quick_view(
            update, context, view="history", title="Історія замовлень"
        )
        return


async def dropper_quick_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    view: str,
    title: str,
) -> None:
    if not update.effective_chat or not update.message:
        return
    ctx: BotContext = context.bot_data["ctx"]
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id if update.effective_user else None
    role, need_reg = _session_role(ctx, update)
    reply_kb = build_reply_keyboard(role, need_registration=need_reg)

    if role != "dropper":
        await update.message.reply_text(
            "Ця кнопка доступна лише в чаті зареєстрованого дроппера.",
            reply_markup=reply_kb,
        )
        return

    webapp_url = ctx.settings.webapp_url
    if not webapp_url:
        await update.message.reply_text(
            "Mini App ще не налаштовано (`WEBAPP_URL`).",
            reply_markup=reply_kb,
        )
        return

    inline = InlineKeyboardMarkup(
        [
            [
                _webapp_button(
                    title,
                    webapp_url,
                    chat_type,
                    chat_id=chat_id,
                    user_id=user_id,
                    view=view,
                )
            ]
        ]
    )
    await _reply_menu_and_inline(
        update.message,
        text=f"{title}:",
        reply_kb=reply_kb,
        inline=inline,
    )


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
    reply_kb = build_reply_keyboard(role, need_registration=need_registration)

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
            reply_markup=reply_kb,
        )
        return

    if role == "owner":
        inline = InlineKeyboardMarkup(
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
            ]
        )
        await _reply_menu_and_inline(
            update.message,
            text="Меню власника:\n\nКерування дропперами та співробітниками.",
            reply_kb=reply_kb,
            inline=inline,
        )
        return

    if role == "warehouse":
        inline = InlineKeyboardMarkup(
            [
                [
                    _webapp_button(
                        "Кабінет комірника",
                        webapp_url,
                        chat_type,
                        chat_id=chat_id,
                        user_id=user_id,
                    )
                ]
            ]
        )
        await _reply_menu_and_inline(
            update.message,
            text="Меню комірника:\n\nКаталог, пакування та друк накладних.",
            reply_kb=reply_kb,
            inline=inline,
        )
        return

    if role in {"admin", "manager"}:
        await update.message.reply_text(
            f"Роль: {role}.\nКабінет співробітника з’явиться наступним етапом.",
            reply_markup=reply_kb,
        )
        return

    if role == "dropper":
        inline = InlineKeyboardMarkup(
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
        await _reply_menu_and_inline(
            update.message,
            text="Меню:",
            reply_kb=reply_kb,
            inline=inline,
        )
        return

    if role == "dropper_blocked":
        await update.message.reply_text(
            "⛔ Вас заблоковано для повного погашення боргу.\n"
            "Передача замовлень недоступна. Звʼяжіться з власником.",
            reply_markup=reply_kb,
        )
        return

    if need_registration:
        inline = InlineKeyboardMarkup(
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
        await _reply_menu_and_inline(
            update.message,
            text=(
                "Цю групу ще не зареєстровано як дроппера.\n"
                "Натисніть кнопку нижче, щоб пройти реєстрацію один раз."
            ),
            reply_kb=reply_kb,
            inline=inline,
        )
        return

    await update.message.reply_text(
        "Меню недоступне в цьому чаті.\n"
        f"chat_id: `{chat_id}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_kb,
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
