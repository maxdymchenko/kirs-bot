import logging

from telegram import Update
from telegram.ext import Application

from bot.core import BotContext
from bot.handlers import register_handlers

logger = logging.getLogger(__name__)


async def start_telegram_app(ctx: BotContext) -> Application:
    application = (
        Application.builder()
        .token(ctx.settings.telegram_token)
        .build()
    )
    application.bot_data["ctx"] = ctx
    register_handlers(application, ctx)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info(
        "Telegram polling запущен. drop_order_chats=%s webapp=%s",
        ctx.settings.drop_order_chat_ids,
        ctx.settings.webapp_url or "-",
    )
    return application


async def stop_telegram_app(application: Application) -> None:
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Telegram polling остановлен")
