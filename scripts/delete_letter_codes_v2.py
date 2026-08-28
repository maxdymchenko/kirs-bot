"""Delete letter codes from the '89 missing' subset, keep 612*."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CREDS_PATH = Path(
    r"C:\Мой компьютер\Мои проекты(Программы)\Kirs_bot\midyear-respect-502706-i6-c5ddff36cd28.json"
)
SPREADSHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"

KEEP = {
    "612Б",
    "612БЕ",
    "612Ж",
    "612КБ",
    "612М",
    "612Н",
    "612Р",
    "612ЧБ",
}

DELETE_CODES = {
    "329Б",
    "329В",
    "347А",
    "347Б",
    "347В",
    "347Г",
    "347Д",
    "347Е",
    "411А",
    "411В",
    "505Ж",
    "505М",
    "505С",
    "505Ч",
    "516А",
    "516Б",
    "516Д",
    "516Ж",
    "516Л",
    "516Т",
    "516ТБ",
    "516ТЧ",
    "516Ч",
    "556К",
    "571Г",
    "571Р",
    "571С",
    "571Ч",
    "601Ч",
    "621К",
    "621М",
    "621Ч",
    "629К",
    "629Ф",
    "629Ч",
    "632К",
    "932Г",
    "932Р",
    "959-1К",
    "1168ГГ",
    "1168ГФ",
    "1168МФ",
    "1184ГЧ",
    "1184КЛ",
    "1184ЛВ",
    "1388Ж",
    "1388М",
}

DELETE_CODES -= KEEP


def with_retry(fn, retries: int = 8):
    for attempt in range(retries):
        try:
            return fn()
        except APIError as exc:
            if "429" not in str(exc) and "Quota" not in str(exc):
                raise
            wait = 15 * (attempt + 1)
            print(f"Квота API, жду {wait} сек...")
            time.sleep(wait)
    return fn()


def main() -> None:
    print(f"К удалению: {len(DELETE_CODES)} кодов")
    print(f"Сохраняем: {', '.join(sorted(KEEP))}")

    creds = Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).sheet1

    print("Читаю таблицу...")
    all_rows = with_retry(lambda: ws.get_all_values())
    header = all_rows[0]
    kept = [header]
    removed = 0
    matched: set[str] = set()
    kept_exceptions: set[str] = set()

    for row in all_rows[1:]:
        code = row[1].strip().lstrip("'") if len(row) > 1 and row[1] else ""
        if code in KEEP:
            kept_exceptions.add(code)
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            kept.append(row[: len(header)])
            continue
        if code in DELETE_CODES:
            removed += 1
            matched.add(code)
            continue
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        kept.append(row[: len(header)])

    print(f"Было строк: {len(all_rows) - 1}")
    print(f"Удаляем: {removed}")
    print(f"Останется: {len(kept) - 1}")
    print(f"Найдено кодов к удалению: {len(matched)}")
    if matched:
        print(f"  {', '.join(sorted(matched))}")
    print(f"Сохранённые 612*: {sorted(kept_exceptions)}")

    not_found = sorted(DELETE_CODES - matched)
    if not_found:
        print(f"Уже нет в таблице ({len(not_found)}): {', '.join(not_found)}")

    if removed == 0:
        print("Нечего удалять — всё уже убрано ранее.")
        return

    for row in kept[1:]:
        if len(row) > 1 and row[1]:
            code = str(row[1]).lstrip("'")
            row[1] = f"'{code}"

    print("Очищаю лист и записываю обратно...")
    with_retry(lambda: ws.clear())
    chunk = 1000
    for start in range(0, len(kept), chunk):
        part = kept[start : start + chunk]
        start_row = start + 1
        print(f"  Пишу строки {start_row}-{start + len(part)}...")
        with_retry(
            lambda part=part, start_row=start_row: ws.update(
                values=part,
                range_name=f"A{start_row}",
                value_input_option="USER_ENTERED",
            )
        )
        time.sleep(1)

    print("Готово.")
    print(f"Удалено строк: {removed}")
    print(f"Строк сейчас: {len(kept) - 1}")


if __name__ == "__main__":
    main()
