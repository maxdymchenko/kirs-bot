# Kirs Bot — универсальный Telegram-бот

Модульный Telegram-бот. Первый модуль — мониторинг почты OLX и уведомления менеджерам.

**Работает 24/7 на Render** (Background Worker), не зависит от вашего ПК.

> Полная инструкция по настройке и передаче знакомому: **[HANDOFF.md](HANDOFF.md)**

## Что делает бот

1. Подключается к единому почтовому ящику по IMAP
2. Проверяет новые письма OLX (каждые 60 сек)
3. Извлекает email аккаунта и ссылку на чат с клиентом
4. Отправляет в Telegram-чат сообщение с кнопкой **«Перейти в чат»**

```
📩 Новое сообщение на OLX

📧 Аккаунт: seller1@gmail.com
💬 Ссылка: https://www.olx.ua/messages/thread/abc123
```

## Быстрый деплой (Render)

1. Залить код на GitHub репозиторий знакомого
2. Render → **New Blueprint** → подключить репо (используется `render.yaml`)
3. Задать секреты в **Environment Variables** (см. `.env.example`)
4. Дождаться статуса **Live** и проверить логи

Подробно: [HANDOFF.md](HANDOFF.md)

## Переменные окружения

| Переменная | Кто предоставляет | Описание |
|------------|-------------------|----------|
| `TELEGRAM_BOT_TOKEN` | Знакомый (BotFather) | Токен бота |
| `TELEGRAM_CHAT_ID` | Вы (утилита `get_chat_id.py`) | ID чата для уведомлений |
| `EMAIL_USER` | Почта знакомого | Единый ящик |
| `EMAIL_PASSWORD` | Вы (пароль приложения) | IMAP-пароль |
| `EMAIL_HOST` | По умолчанию `imap.gmail.com` | IMAP-сервер |
| `EMAIL_PORT` | По умолчанию `993` | IMAP-порт |

## Локальная разработка (у вас на ПК)

Только для тестов и правок кода. В продакшене бот крутится на Render.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Узнать chat_id: `python scripts/get_chat_id.py`

## Настройка (`config.yaml`)

| Параметр | Описание |
|----------|----------|
| `poll_interval` | Интервал проверки почты (сек) |
| `subject_filter` | Фильтр по теме (`olx`) |
| `sender_filter` | Фильтр по отправителю |
| `message_template` | Текст уведомления в Telegram |
| `button_text` | Текст кнопки |
| `patterns` | Регулярки для извлечения ссылки и email |

Переменные шаблона: `{account_email}`, `{chat_link}`, `{subject}`, `{from_email}`

## Структура проекта

```
Kirs_bot/
├── main.py              # Точка входа
├── render.yaml          # Конфиг деплоя Render
├── config.yaml          # Настройки модулей
├── HANDOFF.md           # Инструкция передачи знакомому
├── scripts/
│   └── get_chat_id.py   # Утилита первичной настройки
├── bot/                 # Ядро бота
└── modules/
    └── email_olx/       # Модуль OLX-почты
```

## Стоимость

- **Render Starter Worker:** ~$7/мес (нужен для 24/7)
- Telegram, GitHub: бесплатно
