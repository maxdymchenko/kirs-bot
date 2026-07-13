import json
import os
import sys
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token:
    print("TELEGRAM_BOT_TOKEN не задан")
    sys.exit(1)

url = f"https://api.telegram.org/bot{token}/getUpdates"
with urllib.request.urlopen(url, timeout=30) as response:
    data = json.load(response)

if not data.get("ok"):
    print("Ошибка API Telegram")
    sys.exit(1)

updates = data.get("result", [])
if not updates:
    print("Нет сообщений. Напишите боту /start в нужном чате.")
    sys.exit(0)

seen = set()
for update in updates:
    message = update.get("message") or update.get("channel_post")
    if not message:
        continue
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id in seen:
        continue
    seen.add(chat_id)
    print(f"chat_id: {chat_id}")
    print(f"тип чата: {chat.get('type')}")
    if chat.get("title"):
        print(f"название: {chat.get('title')}")
    print()
