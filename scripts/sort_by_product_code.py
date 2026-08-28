"""Sort Google Sheet rows by column B (product code), smart/natural ascending."""

from __future__ import annotations

import re
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
CODE_COL = 1  # B


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


def clean_code(raw: str) -> str:
    return str(raw or "").strip().lstrip("'")


def smart_sort_key(code: str) -> tuple:
    """
    Natural key: digit groups as ints, text casefold.
    Empty codes sort last via outer tuple in main (not here).
    """
    parts: list[tuple] = []
    for token in re.split(r"(\d+)", code):
        if not token:
            continue
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token.casefold()))
    return tuple(parts)


def main() -> None:
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
    if not all_rows:
        print("Таблица пуста")
        return

    header = all_rows[0]
    width = len(header)
    data = []
    for row in all_rows[1:]:
        if len(row) < width:
            row = row + [""] * (width - len(row))
        else:
            row = row[:width]
        data.append(row)

    before_codes = [clean_code(r[CODE_COL] if len(r) > CODE_COL else "") for r in data]

    # Stable sort: empty B last; among equal keys preserve relative order
    def row_key(row: list[str]) -> tuple:
        code = clean_code(row[CODE_COL] if len(row) > CODE_COL else "")
        if not code:
            return (1,)
        return (0, smart_sort_key(code))

    sorted_data = sorted(data, key=row_key)
    after_codes = [clean_code(r[CODE_COL] if len(r) > CODE_COL else "") for r in sorted_data]

    moved = sum(1 for a, b in zip(before_codes, after_codes) if a != b)
    empty_count = sum(1 for c in after_codes if not c)
    print(f"Строк данных: {len(sorted_data)}")
    print(f"Позиций, где код изменился после сортировки: {moved}")
    print(f"Пустых кодов (в конец): {empty_count}")
    print("Первые 15 кодов после сортировки:")
    for c in after_codes[:15]:
        print(f"  {c!r}")
    print("Последние 10 кодов:")
    for c in after_codes[-10:]:
        print(f"  {c!r}")

    if before_codes == after_codes:
        print("Уже отсортировано — запись не нужна.")
        return

    # Preserve leading zeros as text
    for row in sorted_data:
        if row[CODE_COL]:
            code = clean_code(row[CODE_COL])
            row[CODE_COL] = f"'{code}" if code else ""

    kept = [header] + sorted_data
    print("Очищаю лист и записываю обратно...")
    with_retry(lambda: ws.clear())
    chunk = 1000
    for start in range(0, len(kept), chunk):
        part = kept[start : start + chunk]
        start_row = start + 1
        end_row = start + len(part)
        print(f"  Пишу строки {start_row}-{end_row}...")
        with_retry(
            lambda part=part, start_row=start_row: ws.update(
                values=part,
                range_name=f"A{start_row}",
                value_input_option="USER_ENTERED",
            )
        )
        time.sleep(1)

    print("Готово.")


if __name__ == "__main__":
    main()
