"""Fix Google Sheet column B (Код товара) — restore leading zeros from Excel."""

from __future__ import annotations

import sys
from pathlib import Path

import gspread
import openpyxl
from google.oauth2.service_account import Credentials

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXCEL_PATH = Path(r"C:\Users\brett\Downloads\export-products-15-07-26_10-31-25 (1).xlsx")
SHEET_NAME = "Export Products Sheet"
CREDS_PATH = Path(r"C:\Мой компьютер\Мои проекты(Программы)\Kirs_bot\midyear-respect-502706-i6-c5ddff36cd28.json")
SPREADSHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"

COL_CODE = 1  # A Код_товара
COL_ID = 25  # Y Уникальный_идентификатор


def build_id_to_code() -> dict[str, str]:
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]
    result: dict[str, str] = {}
    for row in ws.iter_rows(min_row=2, max_col=COL_ID, values_only=True):
        if not row:
            continue
        product_id = row[COL_ID - 1]
        code = row[COL_CODE - 1]
        if product_id is None or code is None:
            continue
        # Preserve as string exactly (leading zeros)
        code_str = str(code).strip()
        # If Excel stored as number somehow, try to recover — but openpyxl usually keeps text
        result[str(product_id).strip()] = code_str
    wb.close()
    return result


def main() -> None:
    print("Читаю коды из Excel...")
    id_to_code = build_id_to_code()
    samples = list(id_to_code.items())[:5]
    print(f"Товаров: {len(id_to_code)}")
    print("Примеры Excel:", samples)

    creds = Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).sheet1

    ids = ws.col_values(1)
    existing_codes = ws.col_values(2)
    while len(existing_codes) < len(ids):
        existing_codes.append("")

    updates: list[list[str]] = []
    fixed = 0
    preserved = 0
    unchanged = 0

    for i, raw_id in enumerate(ids):
        if i == 0:
            updates.append([existing_codes[i]])
            continue

        product_id = str(raw_id).strip() if raw_id else ""
        current = existing_codes[i] if i < len(existing_codes) else ""

        if not product_id:
            updates.append([current])
            preserved += 1
            continue

        if product_id not in id_to_code:
            updates.append([current])
            continue

        code = id_to_code[product_id]
        # Force text in Sheets so leading zeros stay
        cell_value = f"'{code}" if code and not code.startswith("'") else code
        # Actually USER_ENTERED with leading apostrophe makes it text.
        # Better: write as string with apostrophe prefix for Sheets text.
        updates.append([f"'{code}"])
        if str(current).lstrip("'") != code:
            fixed += 1
        else:
            unchanged += 1

    values = updates[1:]
    end_row = 1 + len(values)
    print(f"Пишу коды в B2:B{end_row}...")
    ws.update(values=values, range_name=f"B2:B{end_row}", value_input_option="USER_ENTERED")

    print("Готово.")
    print(f"  Исправлено (отличались): {fixed}")
    print(f"  Уже совпадали: {unchanged}")
    print(f"  Старые строки без ID сохранены: {preserved}")

    # Verify a few
    check = ws.get("A11:B15")
    print("Проверка A11:B15:")
    for row in check:
        print(f"  {row}")


if __name__ == "__main__":
    main()
