"""Утилита для получения TELEGRAM_CHAT_ID при первичной настройке.

Использование:
  1. Знакомый создаёт бота и присылает TELEGRAM_BOT_TOKEN
  2. Добавьте бота в нужный чат (или напишите /start в личку)
  3. Запустите: python scripts/get_chat_id.py
  4. Напишите что-нибудь боту в чате — скрипт покажет chat_id
"""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Задайте TELEGRAM_BOT_TOKEN в .env или переменных окружения")
        sys.exit(1)

    print("Ожидаю сообщение в чат с ботом...", flush=True)
    print("Напишите боту /start или любое сообщение в нужном чате.\n", flush=True)

    async def on_message(update: Update, context) -> None:
        chat = update.effective_chat
        if not chat:
            return
        print(f"chat_id: {chat.id}", flush=True)
        print(f"тип чата: {chat.type}", flush=True)
        if chat.title:
            print(f"название: {chat.title}", flush=True)
        print("\nСкопируйте chat_id в TELEGRAM_CHAT_ID на Render.", flush=True)
        await context.application.stop()

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
