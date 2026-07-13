from abc import ABC, abstractmethod
from typing import Any


class BaseModule(ABC):
    """Базовый класс для подключаемых модулей бота."""

    name: str = "base"

    def __init__(self, config: dict[str, Any], bot_context: "BotContext"):
        self.config = config
        self.ctx = bot_context

    @abstractmethod
    async def start(self) -> None:
        """Запуск модуля (фоновые задачи, обработчики и т.д.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Остановка модуля."""
