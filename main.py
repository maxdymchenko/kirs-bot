import asyncio
import logging
import os
import signal
import sys

import uvicorn

from bot.catalog import CatalogService
from bot.core import BotContext, load_settings
from bot.runner import create_modules, run_modules
from bot.telegram_app import start_telegram_app, stop_telegram_app
from bot.webapp import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    from bot.accounts import AppStorage

    app_storage = AppStorage()
    ctx = BotContext(settings, app_storage=app_storage)
    catalog = CatalogService()

    # Прогрев каталога (не падаем, если Sheets временно недоступен)
    try:
        await asyncio.to_thread(catalog.refresh, True)
    except Exception:
        logger.exception("Не удалось заранее загрузить каталог — поиск попробует позже")

    web = create_web_app(catalog, settings, app_storage)
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(web, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve(), name="web")

    telegram_app = await start_telegram_app(ctx)
    modules = create_modules(ctx)

    if not modules:
        logger.error("Нет активных модулей. Проверьте config.yaml")
        server.should_exit = True
        await web_task
        await stop_telegram_app(telegram_app)
        sys.exit(1)

    logger.info(
        "Бот запущен. Модулей: %d. Mini App: %s",
        len(modules),
        settings.webapp_url or f"http://0.0.0.0:{port}",
    )

    stop_event = asyncio.Event()

    def request_stop(*_args) -> None:
        logger.info("Получен сигнал остановки...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, request_stop)

    run_task = asyncio.create_task(run_modules(modules), name="modules")
    stop_task = asyncio.create_task(stop_event.wait(), name="stop")

    done, _ = await asyncio.wait(
        {run_task, stop_task, web_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    server.should_exit = True
    if stop_task in done or web_task in done:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    for module in modules:
        await module.stop()

    await stop_telegram_app(telegram_app)
    if not web_task.done():
        await web_task
    logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except ValueError as exc:
        logger.error("Ошибка конфигурации: %s", exc)
        sys.exit(1)
