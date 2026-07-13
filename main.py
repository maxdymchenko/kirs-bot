import asyncio
import logging
import signal
import sys

from bot.core import BotContext, load_settings
from bot.runner import create_modules, run_modules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    ctx = BotContext(settings)
    modules = create_modules(ctx)

    if not modules:
        logger.error("Нет активных модулей. Проверьте config.yaml")
        sys.exit(1)

    logger.info("Бот запущен. Активных модулей: %d", len(modules))

    stop_event = asyncio.Event()

    def request_stop(*_args) -> None:
        logger.info("Получен сигнал остановки...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler для SIGTERM
            signal.signal(sig, request_stop)

    run_task = asyncio.create_task(run_modules(modules))
    stop_task = asyncio.create_task(stop_event.wait())

    done, _ = await asyncio.wait(
        {run_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_task in done:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    for module in modules:
        await module.stop()

    logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except ValueError as exc:
        logger.error("Ошибка конфигурации: %s", exc)
        sys.exit(1)
