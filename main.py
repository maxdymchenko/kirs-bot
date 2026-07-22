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
        "Бот запущен. Модулей: %d. Mini App: %s. Data: %s. Notifications DB: %s",
        len(modules),
        settings.webapp_url or f"http://0.0.0.0:{port}",
        app_storage.db_path.parent,
        ctx.storage.db_path,
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

    async def _np_notify(chat_id: str, text: str) -> None:
        if not chat_id or not text:
            return
        try:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("NP notify failed for %s", chat_id)

    async def _np_owner_notify(text: str) -> None:
        if not text:
            return
        targets: list[str] = []
        for chat in settings.owner_chat_ids:
            resolved = app_storage.resolve_chat_id(chat) or chat
            if resolved and resolved not in targets:
                targets.append(resolved)
        for user in settings.owner_user_ids:
            if user and str(user) not in targets:
                targets.append(str(user))
        for target in targets:
            await _np_notify(target, text)

    async def np_maintenance_loop() -> None:
        from bot.np_fulfillment import run_np_maintenance_once

        await asyncio.sleep(20)
        while not stop_event.is_set():
            try:
                stats = await run_np_maintenance_once(
                    app_storage,
                    notify=_np_notify,
                    owner_notify=_np_owner_notify,
                )
                # Ретрай створення ТТН + опитування статусів раз на 30 хв
                if any(
                    stats.get(k)
                    for k in (
                        "create_ok",
                        "create_fail",
                        "backup_used",
                        "updated",
                        "received",
                        "returned",
                        "checked",
                        "errors",
                    )
                ):
                    logger.info("NP maintenance: %s", stats)
            except Exception:
                logger.exception("NP maintenance loop error")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1800)
            except asyncio.TimeoutError:
                pass

    async def warehouse_reminders_loop() -> None:
        """О 10:00 Київ — разові нагадування на 5-й і 7-й день на відділенні."""
        from bot.warehouse_reminders import (
            run_warehouse_reminders_pass,
            seconds_until_next_notify_hour,
        )

        await asyncio.sleep(45)
        while not stop_event.is_set():
            try:
                delay = seconds_until_next_notify_hour(allow_current_hour=True)
                if delay > 0:
                    logger.info(
                        "Warehouse reminders: next pass in %.0f min", delay / 60.0
                    )
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=delay)
                        break
                    except asyncio.TimeoutError:
                        pass
                stats = await run_warehouse_reminders_pass(
                    app_storage, notify=_np_notify
                )
                logger.info("Warehouse reminders: %s", stats)
                # Наступний прохід — завтра о 10:00 (не в межах тієї ж години)
                delay = seconds_until_next_notify_hour(allow_current_hour=False)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass
            except Exception:
                logger.exception("Warehouse reminders loop error")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    pass

    run_task = asyncio.create_task(run_modules(modules, ctx), name="modules")
    np_task = asyncio.create_task(np_maintenance_loop(), name="np-maintenance")
    warehouse_task = asyncio.create_task(
        warehouse_reminders_loop(), name="warehouse-reminders"
    )
    stop_task = asyncio.create_task(stop_event.wait(), name="stop")

    done, _ = await asyncio.wait(
        {run_task, stop_task, web_task, np_task, warehouse_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    server.should_exit = True
    stop_event.set()
    for task in (run_task, np_task, warehouse_task):
        if not task.done():
            task.cancel()
            try:
                await task
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
