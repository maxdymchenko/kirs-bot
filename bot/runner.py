import asyncio
import logging
from typing import TYPE_CHECKING

from modules.base import BaseModule
from modules.email_olx import EmailOlxModule

if TYPE_CHECKING:
    from bot.core import BotContext

logger = logging.getLogger(__name__)

MODULE_REGISTRY: dict[str, type[BaseModule]] = {
    "email_olx": EmailOlxModule,
}


def create_modules(ctx: "BotContext") -> list[BaseModule]:
    modules: list[BaseModule] = []
    for name, module_cls in MODULE_REGISTRY.items():
        config = ctx.settings.modules_config.get(name, {})
        if not config.get("enabled", False):
            logger.info("Модуль %s отключён", name)
            continue
        modules.append(module_cls(config, ctx))
        logger.info("Модуль %s подключён", name)
    return modules


async def _credit_holidays_loop(ctx: "BotContext") -> None:
    from bot.credit_holidays import run_credit_holidays_pass
    import json
    import urllib.request

    async def notify(chat_id: str, text: str) -> None:
        token = ctx.settings.telegram_token

        def _send() -> None:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps(
                {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()

        await asyncio.to_thread(_send)

    # перша перевірка через хвилину після старту, далі щогодини
    await asyncio.sleep(60)
    while True:
        try:
            stats = await run_credit_holidays_pass(ctx.app_storage, notify)
            logger.info("Credit holidays pass: %s", stats)
        except Exception:
            logger.exception("Credit holidays pass failed")
        await asyncio.sleep(3600)


async def run_modules(modules: list[BaseModule], ctx: "BotContext | None" = None) -> None:
    for module in modules:
        await module.start()

    holidays_task = None
    if ctx is not None:
        holidays_task = asyncio.create_task(
            _credit_holidays_loop(ctx), name="credit-holidays"
        )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        if holidays_task:
            holidays_task.cancel()
            try:
                await holidays_task
            except asyncio.CancelledError:
                pass
