import logging

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
    await application.updater.start_polling(drop_pending_updates=False)
    logger.info("Telegram polling запущен")
    return application


async def stop_telegram_app(application: Application) -> None:
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Telegram polling остановлен")
