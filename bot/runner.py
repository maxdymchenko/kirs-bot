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


async def run_modules(modules: list[BaseModule]) -> None:
    for module in modules:
        await module.start()

    while True:
        await asyncio.sleep(3600)
